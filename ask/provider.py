from abc import ABC, abstractmethod
import requests
import json
import sys
from typing import List, Dict, Any, Optional
from ask.tools import format_for_openai


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
        normalized.append({
            "name": name,
            "arguments": arguments,
        })
    return normalized


class Provider(ABC):
    @abstractmethod
    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        pass
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None) -> bool:
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

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL

    @classmethod
    def get_available_models(cls, base_url: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/api/tags"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None) -> bool:
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

    def _chat_streaming(self, payload: dict) -> dict:
        """Handle Ollama responses. For 'stream: false', it's a single JSON response.
        For actual streaming (which models may do), we accumulate chunks."""
        url = f"{self.base_url}/api/chat"
        
        try:
            payload["stream"] = False
            response = requests.post(url, json=payload)
            
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
            
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Ollama at {self.base_url}. Is it running?", "tool_calls": []}
        except requests.exceptions.HTTPError as e:
            detail = response.text.strip()
            suffix = f": {detail}" if detail else ""
            return {"content": f"Error: LLM provider returned an HTTP error: {e}{suffix}", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/api/chat"
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        effective_tools = []
        if tools and self.supports_tools(self.base_url, self.model):
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        return self._chat_streaming(payload)


class LMStudioProvider(Provider):
    DEFAULT_BASE_URL = "http://localhost:1234"
    DEFAULT_MODEL = "local-model"

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL

    @classmethod
    def get_available_models(cls, base_url: str = None) -> list[str]:
        url = f"{(base_url or cls.DEFAULT_BASE_URL).rstrip('/')}/v1/models"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []
    
    @classmethod
    def supports_tools(cls, base_url: str = None, model: str = None) -> bool:
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
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        effective_tools = []
        if tools and self.supports_tools(self.base_url, self.model):
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
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

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> str:
        return ""

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
    def supports_tools(cls, base_url: str = None, model: str = None) -> bool:
        """Anthropic models support tool calling via beta headers."""
        return True

    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        url = f"{self.base_url}/messages"
        
        anthropic_messages = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    anthropic_messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    anthropic_messages.append({"role": "assistant", "content": content})
        
        anthropic_messages.append({"role": "user", "content": query})

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": 1024,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        effective_tools = []
        if tools and self.supports_tools(self.base_url, self.model):
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
            response = requests.post(url, json=payload, headers=headers)
            
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
            
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Anthropic at {self.base_url}. Is it reachable?", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}


class ChatGPTProvider(Provider):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4"

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> str:
        return ""

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
    def supports_tools(cls, base_url: str = None, model: str = None) -> bool:
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
                headers={"Authorization": f"Bearer test"},
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
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        effective_tools = []
        if tools and self.supports_tools(self.base_url, self.model):
            effective_tools = [format_for_openai(t) for t in tools]
        elif tools:
            print(f"Warning: Model '{self.model}' does not support native tool calling. Tools will be ignored.", file=sys.stderr)
        
        if effective_tools:
            payload["tools"] = effective_tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
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
            
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to ChatGPT at {self.base_url}. Is it reachable?", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}
