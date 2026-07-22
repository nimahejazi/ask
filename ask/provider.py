from abc import ABC, abstractmethod
import requests
import json
from typing import List, Dict, Any, Optional
from ask.tools import format_for_openai

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
            
            # If we get 400 with tools, model likely doesn't support them
            if response.status_code == 400:
                return False
            
            # If we get any other successful response, model supports tools
            return True
                
        except Exception:
            # If we can't test, assume tools are supported
            return True

    def _chat_streaming(self, payload: dict) -> dict:
        """Handle Ollama responses. For 'stream: false', it's a single JSON response.
        For actual streaming (which models may do), we accumulate chunks."""
        url = f"{self.base_url}/api/chat"
        
        try:
            # Send with stream: false to get single response
            payload["stream"] = False
            response = requests.post(url, json=payload)
            
            # Check for HTTP errors before processing
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    if "error" in error_data and "not found" in str(error_data).lower():
                        return {"content": f"Error: Model '{self.model}' not found. Please run 'ollama pull {self.model}' or check your config.", "tool_calls": []}
                except (json.JSONDecodeError, KeyError):
                    pass
                return {"content": f"Error: LLM endpoint not found ({url}). Please ensure Ollama is installed and updated to the latest version.", "tool_calls": []}
            
            response.raise_for_status()
            
            # Try to parse as single JSON response (stream: false)
            try:
                data = response.json()
                message = data.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
                return {"content": content, "tool_calls": tool_calls}
            except json.JSONDecodeError:
                # If not valid JSON, try streaming mode (models sometimes stream even with stream: false)
                pass
            
            # Fall back to streaming mode - accumulate chunks
            full_content = ""
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    try:
                        chunk = json.loads(line_str)
                        message = chunk.get("message", {})
                        content = message.get("content", "")
                        full_content += content
                        
                        # Check if this is the final chunk
                        if chunk.get("done", False):
                            tool_calls = message.get("tool_calls", [])
                            return {"content": full_content, "tool_calls": tool_calls}
                    except json.JSONDecodeError:
                        continue
            
            return {"content": full_content, "tool_calls": []}
            
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Ollama at {self.base_url}. Is it running?", "tool_calls": []}
        except requests.exceptions.HTTPError as e:
            return {"content": f"Error: LLM provider returned an HTTP error: {e}", "tool_calls": []}
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
            "stream": False  # We'll use streaming mode to handle the response
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
            
            if response.status_code == 400:
                return False
            
            return True
                
        except Exception:
            return True

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
        tool_calls = message.get("tool_calls", [])
        return {"content": content, "tool_calls": tool_calls}
