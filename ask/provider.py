from abc import ABC, abstractmethod
import requests
import json
from typing import List, Dict, Any, Optional
from ask.tools import format_for_openai

class Provider(ABC):
    @abstractmethod
    def chat(self, query: str, system_prompt: str = "", history: list[dict] = None, tools: List[Dict[str, Any]] = None) -> dict:
        pass

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
        
        if tools:
            payload["tools"] = [format_for_openai(t) for t in tools]

        try:
            response = requests.post(url, json=payload)
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    if "error" in error_data and "not found" in error_data["error"].lower():
                        return {"content": f"Error: Model '{self.model}' not found. Please run 'ollama pull {self.model}' or check your config.", "tool_calls": []}
                except (json.JSONDecodeError, KeyError):
                    pass
                return {"content": f"Error: LLM endpoint not found ({url}). Please ensure Ollama is installed and updated to the latest version.", "tool_calls": []}
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            return {"content": f"Error: Could not connect to Ollama at {self.base_url}. Is it running?", "tool_calls": []}
        except requests.exceptions.HTTPError as e:
            return {"content": f"Error: LLM provider returned an HTTP error: {e}", "tool_calls": []}
        except Exception as e:
            return {"content": f"An unexpected error occurred: {e}", "tool_calls": []}
        
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        return {"content": content, "tool_calls": tool_calls}

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

        if tools:
            payload["tools"] = [format_for_openai(t) for t in tools]

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
