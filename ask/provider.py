from abc import ABC, abstractmethod
import requests
import json

class Provider(ABC):
    @abstractmethod
    def chat(self, query: str, system_prompt: str = "") -> str:
        pass

class MockProvider(Provider):
    def chat(self, query: str, system_prompt: str = "") -> str:
        return f"Mock response to: {query}"

class OllamaProvider(Provider):
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3"

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL

    def chat(self, query: str, system_prompt: str = "") -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 404:
                try:
                    error_data = response.json()
                    if "error" in error_data and "not found" in error_data["error"].lower():
                        return f"Error: Model '{self.model}' not found. Please run 'ollama pull {self.model}' or check your config."
                except (json.JSONDecodeError, KeyError):
                    pass
                return (f"Error: LLM endpoint not found ({url}). "
                        "Please ensure Ollama is installed and updated to the latest version.")
            response.raise_for_status()

        except requests.exceptions.ConnectionError:
            return f"Error: Could not connect to Ollama at {self.base_url}. Is it running?"
        except requests.exceptions.HTTPError as e:
            return f"Error: LLM provider returned an HTTP error: {e}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"
        
        data = response.json()
        return data["message"]["content"]


