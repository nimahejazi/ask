from abc import ABC, abstractmethod
import requests
import json
import sys
import os
from typing import List, Dict, Any, Optional, Iterator, Tuple
from ask.tools import format_for_openai

DEFAULT_REQUEST_TIMEOUT = 120

class ProviderError(Exception):
    """Raised when a provider call fails (auth, connection, timeout, http error)."""
    pass


def normalize_tool_calls(tool_calls: list[dict]) -> list[dict]:
    normalized = []
    for tool_call in tool_calls:
        function = tool_call.get("function", tool_call)
        name = function.get("name", "")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid tool call arguments for '{name}': {error}"
                ) from error
        if not isinstance(arguments, dict):
            raise ValueError(
                f"Invalid tool call arguments for '{name}': expected an object"
            )
        entry = {
            "name": name,
            "arguments": arguments,
        }
        # Preserve tool call id for native protocol (OpenAI, Anthropic)
        if "id" in tool_call:
            entry["id"] = tool_call["id"]
        elif function.get("id"):
            entry["id"] = function["id"]
        normalized.append(entry)
    return normalized


def resolve_max_tokens(raw: Any, warn: bool = True) -> Optional[int]:
    """Validate max_tokens value. Returns int or None (meaning use default).
    Prints a warning to stderr for nonsense values and returns None or clamped value.
    """
    if raw is None:
        return None
    try:
        # Allow numeric strings
        val = int(raw) if not isinstance(raw, bool) else int(raw)
        # But reject booleans explicitly
        if isinstance(raw, bool):
            raise ValueError
    except (ValueError, TypeError):
        if warn:
            print(f"Warning: Invalid max_tokens value '{raw}' — expected a positive integer. Using default.", file=sys.stderr)
        return None
    if val < 1:
        if warn:
            print(f"Warning: max_tokens {val} is too small — must be >=1. Using default.", file=sys.stderr)
        return None
    if val > 100000:
        if warn:
            print(f"Warning: max_tokens {val} is too large — clamped to 100000.", file=sys.stderr)
        return 100000
    return val


def effective_max_tokens_for_anthropic(raw: Any, warn: bool = True) -> int:
    """Anthropic requires max_tokens; default 1024 when not configured or invalid."""
    validated = resolve_max_tokens(raw, warn=warn)
    return validated if validated is not None else 1024


def _build_openai_messages(system_prompt: str, history: Optional[list[dict]], query: str) -> list[dict]:
    """Build messages for OpenAI-compatible APIs, handling native tool protocol."""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Convert stored tool_calls (name, arguments, id) to OpenAI shape
                converted_calls = []
                for idx, tc in enumerate(msg["tool_calls"]):
                    tc_id = tc.get("id") or f"call_{idx}_{tc.get('name','')}"
                    converted_calls.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("arguments", {})),
                        }
                    })
                messages.append({
                    "role": "assistant",
                    "content": msg.get("content", ""),
                    "tool_calls": converted_calls,
                })
            else:
                messages.append(msg)
    if query:
        messages.append({"role": "user", "content": query})
    return messages


def _build_anthropic_messages(history: Optional[list[dict]], query: str) -> list[dict]:
    """Build messages for Anthropic, handling tool_use / tool_result blocks."""
    anthropic_messages: list[dict] = []
    if history:
        for msg in history:
            role = msg.get("role", "")
            if role == "assistant" and msg.get("tool_calls"):
                # Assistant with tool calls -> content blocks with tool_use
                blocks: list[dict] = []
                content = msg.get("content", "")
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in msg["tool_calls"]:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{tc.get('name','')}"),
                        "name": tc.get("name", ""),
                        "input": tc.get("arguments", {}),
                    })
                anthropic_messages.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                # Tool result -> user with tool_result block
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", ""),
                    }]
                })
            elif role == "user":
                # Content may be string or already blocks; handle both
                content = msg.get("content", "")
                if isinstance(content, list):
                    anthropic_messages.append({"role": "user", "content": content})
                else:
                    anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    anthropic_messages.append({"role": "assistant", "content": content})
                else:
                    anthropic_messages.append({"role": "assistant", "content": content})
            else:
                # Fallback: treat as user
                anthropic_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    if query:
        anthropic_messages.append({"role": "user", "content": query})
    return anthropic_messages


from typing import Iterator, Tuple

class Provider(ABC):
    @abstractmethod
    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        pass
    
    def chat_stream(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> Iterator[str]:
        """Generator that yields chunks of the response as they arrive."""
        yield ""
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None, api_key: str = None) -> bool:
        """Check if the model supports tool calling."""
        return False


class MockProvider(Provider):
    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        tool_info = f" (Tools provided: {[t['name'] for t in tools]})" if tools else ""
        response_text = f"Mock response to: {query}{tool_info}"
        return {"content": response_text, "tool_calls": []}


class OllamaProvider(Provider):
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3"

    def __init__(self, base_url: str = None, model: str = None, max_tokens: Any = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._tool_support_cache: Optional[bool] = None

    def _supports_tools_cached(self) -> bool:
        if self._tool_support_cache is None:
            self._tool_support_cache = self.__class__.supports_tools(self.base_url, self.model)
        return self._tool_support_cache

    def chat_stream(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> Iterator[str]:
        url = f"{self.base_url}/api/chat"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["options"] = {"num_predict": _mt}

        try:
            response = requests.post(url, json=payload, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    try:
                        chunk = json.loads(line_str)
                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        if content:
                            yield content
                        full_content += content
                         
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.Timeout:
            raise ProviderError(f"Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})")
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Could not connect to Ollama at {self.base_url}. Is it running?")
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = response.text.strip()
            except Exception:
                pass
            suffix = f": {detail}" if detail else ""
            raise ProviderError(f"LLM provider returned an HTTP error: {e}{suffix}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e))

    @classmethod
    def get_available_models(cls, base_url: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/api/tags"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None, api_key: str = None) -> bool:
        """Check if the model supports tool calling by testing with a simple request."""
        try:
            test_base_url = (base_url or cls.DEFAULT_BASE_URL).rstrip("/")
            test_model = model or "llama3"
            
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "test"}],
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "Test tool",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }],
                "stream": False
            }
            
            url = f"{test_base_url}/api/chat"
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code >= 400:
                return False
            
            return True
                
        except Exception:
            return False

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/api/chat"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["options"] = {"num_predict": _mt}

        try:
            response = requests.post(url, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    error_message = str(error_data.get("error", "")).lower()
                    if "model" in error_message and "not found" in error_message:
                        return {"content": f"Error: Model '{self.model}' not found. Please run 'ollama pull {self.model}' or check your config.", "tool_calls": []}
                except (json.JSONDecodeError, KeyError):
                    pass
                detail = response.text.strip()
                suffix = f" Provider response: {detail}" if detail else ""
                return {"content": f"Error: LLM endpoint not found ({url}). Please ensure Ollama is installed and updated to the latest version.{suffix}", "tool_calls": []}
            
            response.raise_for_status()
            
            try:
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "")
                tool_calls = normalize_tool_calls(message.get("tool_calls", []))
                return {"content": content, "tool_calls": tool_calls}
            except json.JSONDecodeError:
                pass
            
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    try:
                        chunk = json.loads(line_str)
                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        full_content += content
                        
                        if chunk.get("done", False):
                            tool_calls = normalize_tool_calls(message.get("tool_calls", []))
                            return {"content": full_content, "tool_calls": tool_calls}
                    except json.JSONDecodeError:
                        continue
            
            return {"content": full_content, "tool_calls": []}
            
        except requests.exceptions.Timeout:
            return {"content": f"Error: Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})", "tool_calls": []}
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Ollama at {self.base_url}. Is it running?", "tool_calls": []}
        except requests.exceptions.HTTPError as e:
            detail = response.text.strip()
            suffix = f": {detail}" if detail else ""
            return {"content": f"Error: LLM provider returned an HTTP error: {e}{suffix}", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}


class LMStudioProvider(Provider):
    DEFAULT_BASE_URL = "http://localhost:1234"
    DEFAULT_MODEL = "local-model"

    def __init__(self, base_url: str = None, model: str = None, max_tokens: Any = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._tool_support_cache: Optional[bool] = None

    def _supports_tools_cached(self) -> bool:
        if self._tool_support_cache is None:
            self._tool_support_cache = self.__class__.supports_tools(self.base_url, self.model)
        return self._tool_support_cache

    def chat_stream(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> Iterator[str]:
        url = f"{self.base_url}/v1/chat/completions"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True
        }

        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["max_tokens"] = _mt

        try:
            response = requests.post(url, json=payload, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        chunk_str = line_str[6:]
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_str)
                            choice = chunk.get("choices", [])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, IndexError):
                            continue
        except requests.exceptions.Timeout:
            raise ProviderError(f"Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})")
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Could not connect to LM Studio at {self.base_url}. Is it running?")
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = response.text.strip()
            except Exception:
                pass
            suffix = f": {detail}" if detail else ""
            raise ProviderError(f"LLM provider returned an HTTP error: {e}{suffix}")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e))

    @classmethod
    def get_available_models(cls, base_url: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/v1/models"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None, api_key: str = None) -> bool:
        """Check if the model supports tool calling by testing with a simple request."""
        try:
            test_base_url = (base_url or cls.DEFAULT_BASE_URL).rstrip("/")
            test_model = model or "local-model"
            
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "test"}],
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "Test tool",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }]
            }
            
            url = f"{test_base_url}/v1/chat/completions"
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code >= 400:
                return False
            
            return True
                
        except Exception:
            return False

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/v1/chat/completions"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["max_tokens"] = _mt

        try:
            response = requests.post(url, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            return {"content": f"Error: Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})", "tool_calls": []}
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to LM Studio at {self.base_url}. Is it running?", "tool_calls": []}
        except Exception as e:
            return {"content": f"Error connect to LM Studio at {self.base_url}: {e}", "tool_calls": []}
        
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        try:
            tool_calls = normalize_tool_calls(message.get("tool_calls", []))
        except ValueError as error:
            return {"content": f"Error: {error}", "tool_calls": []}
        return {"content": content, "tool_calls": tool_calls}


class AnthropicProvider(Provider):
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-opus-20240229"

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None, max_tokens: Any = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key or self._get_api_key()
        self.max_tokens = max_tokens
        self._tool_support_cache: Optional[bool] = None

    def _supports_tools_cached(self) -> bool:
        if self._tool_support_cache is None:
            self._tool_support_cache = self.__class__.supports_tools(self.base_url, self.model)
        return self._tool_support_cache

    def chat_stream(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> Iterator[str]:
        url = f"{self.base_url}/messages"
        
        anthropic_messages = _build_anthropic_messages(history, query)

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": effective_max_tokens_for_anthropic(self.max_tokens),
            "stream": True
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        effective_tools = []
        if tools and self._supports_tools_cached():
            for tool in tools:
                formatted_tool = format_for_openai(tool)
                anthropic_tool = {
                    "name": formatted_tool.get("name", ""),
                    "description": formatted_tool.get("description", ""),
                    "input_schema": formatted_tool.get("parameters", {})
                }
                effective_tools.append(anthropic_tool)
        
        if effective_tools:
            payload["tools"] = effective_tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        full_content = ""
        try:
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            if response.status_code == 401:
                raise ProviderError("Invalid Anthropic API key. Please check your configuration.")
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = str(error_data.get("error", {}).get("message", ""))
                except (json.JSONDecodeError, KeyError):
                    error_message = response.text
                raise ProviderError(f"Anthropic API returned an error: {error_message}")
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        chunk_str = line_str[6:]
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_str)
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield text
                                full_content += text
                        except (json.JSONDecodeError, KeyError):
                            continue
        except requests.exceptions.Timeout:
            raise ProviderError(f"Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})")
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Could not connect to Anthropic at {self.base_url}. Is it reachable?")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e))

    def _get_api_key(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "")

    @classmethod
    def get_available_models(cls, base_url: str = None, api_key: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/models"
        try:
            response = requests.get(
                url,
                headers={
                    "x-api-key": api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []

    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None, api_key: str = None) -> bool:
        """Anthropic models support tool calling via beta headers."""
        return True

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/messages"
        
        anthropic_messages = _build_anthropic_messages(history, query)

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": effective_max_tokens_for_anthropic(self.max_tokens),
            "stream": False
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        effective_tools = []
        if tools and self._supports_tools_cached():
            for tool in tools:
                formatted_tool = format_for_openai(tool)
                anthropic_tool = {
                    "name": formatted_tool.get("name", ""),
                    "description": formatted_tool.get("description", ""),
                    "input_schema": formatted_tool.get("parameters", {})
                }
                effective_tools.append(anthropic_tool)
        
        if effective_tools:
            payload["tools"] = effective_tools

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            if response.status_code == 401:
                return {"content": "Error: Invalid Anthropic API key. Please check your configuration.", "tool_calls": []}
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = str(error_data.get("error", {}).get("message", ""))
                except (json.JSONDecodeError, KeyError):
                    error_message = response.text
                return {"content": f"Error: Anthropic API returned an error: {error_message}", "tool_calls": []}
            
            response.raise_for_status()
            
            data = response.json()
            content_blocks = data.get("content", [])
            
            final_content = ""
            tool_calls = []
            
            for block in content_blocks:
                if block.get("type") == "text":
                    final_content += block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_call = {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "arguments": block.get("input", {})
                    }
                    tool_calls.append(tool_call)
            
            normalized_tool_calls = []
            for call in tool_calls:
                normalized_tool_calls.append({
                    "name": call.get("name", ""),
                    "arguments": call.get("arguments", {}),
                    "id": call.get("id")
                })
            
            return {"content": final_content, "tool_calls": normalized_tool_calls}
            
        except requests.exceptions.Timeout:
            return {"content": f"Error: Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})", "tool_calls": []}
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Anthropic at {self.base_url}. Is it reachable?", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}


class ChatGPTProvider(Provider):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4"

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None, max_tokens: Any = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key or self._get_api_key()
        self.max_tokens = max_tokens
        self._tool_support_cache: Optional[bool] = None

    def _supports_tools_cached(self) -> bool:
        if self._tool_support_cache is None:
            self._tool_support_cache = self.__class__.supports_tools(self.base_url, self.model, api_key=self.api_key)
        return self._tool_support_cache

    def chat_stream(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True
        }

        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["max_tokens"] = _mt

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            if response.status_code == 401:
                raise ProviderError("Invalid ChatGPT API key. Please check your configuration.")
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = str(error_data.get("error", {}).get("message", ""))
                except (json.JSONDecodeError, KeyError):
                    error_message = response.text
                raise ProviderError(f"ChatGPT API returned an error: {error_message}")
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        chunk_str = line_str[6:]
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(chunk_str)
                            choice = chunk.get("choices", [])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, IndexError):
                            continue
        except requests.exceptions.Timeout:
            raise ProviderError(f"Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})")
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Could not connect to ChatGPT at {self.base_url}. Is it reachable?")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(str(e))

    def _get_api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @classmethod
    def get_available_models(cls, base_url: str = None, api_key: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/models"
        try:
            response = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key or ''}",
                    "content-type": "application/json"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []

    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None, api_key: str = None) -> bool:
        """Check if the model supports tool calling by testing with a simple request."""
        try:
            test_base_url = (base_url or cls.DEFAULT_BASE_URL).rstrip("/")
            test_model = model or "gpt-4"
            
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "test"}],
                "tools": [{
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "Test tool",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }]
            }
            
            url = f"{test_base_url}/chat/completions"
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key or ''}"},
                json=payload,
                timeout=10
            )
            
            if response.status_code >= 400:
                return False
            
            return True
                
        except Exception:
            return False

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        messages = _build_openai_messages(system_prompt, history, query)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }

        effective_tools = []
        if tools and self._supports_tools_cached():
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        _mt = resolve_max_tokens(self.max_tokens)
        if _mt is not None:
            payload["max_tokens"] = _mt

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            if response.status_code == 401:
                return {"content": "Error: Invalid ChatGPT API key. Please check your configuration.", "tool_calls": []}
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = str(error_data.get("error", {}).get("message", ""))
                except (json.JSONDecodeError, KeyError):
                    error_message = response.text
                return {"content": f"Error: ChatGPT API returned an error: {error_message}", "tool_calls": []}
            
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            try:
                tool_calls = normalize_tool_calls(message.get("tool_calls", []))
            except ValueError as error:
                return {"content": f"Error: {error}", "tool_calls": []}
            return {"content": content, "tool_calls": tool_calls}
            
        except requests.exceptions.Timeout:
            return {"content": f"Error: Endpoint did not respond in {DEFAULT_REQUEST_TIMEOUT}s ({self.base_url})", "tool_calls": []}
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to ChatGPT at {self.base_url}. Is it reachable?", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}
