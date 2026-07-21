from abc import ABC, abstractmethod

class Provider(ABC):
    @abstractmethod
    def chat(self, query: str, system_prompt: str = "") -> str:
        pass

class MockProvider(Provider):
    def chat(self, query: str, system_prompt: str = "") -> str:
        return f"Mock response to: {query}"
