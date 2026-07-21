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
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data["message"]["content"]

