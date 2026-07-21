import pytest
import requests_mock
from ask.provider import OllamaProvider

def test_ollama_provider_chat():
    base_url = "http://test-ollama:11434"
    model = "test-model"
    provider = OllamaProvider(base_url=base_url, model=model)
    
    query = "Hello!"
    system_prompt = "You are a helpful assistant."
    expected_response = "Hi there! How can I help you today?"

    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", json={
            "model": model,
            "message": {"role": "assistant", "content": expected_response}
        })

        response = provider.chat(query, system_prompt=system_prompt)
        
        assert response == expected_response
        assert m.called

def test_ollama_provider_model_not_found():
    base_url = "http://test-ollama:11434"
    model = "missing-model"
    provider = OllamaProvider(base_url=base_url, model=model)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=404, json={"error": f"model '{model}' not found"})

        response = provider.chat("Hello!")
        assert f"Error: Model '{model}' not found" in response

def test_ollama_provider_endpoint_not_found():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=404, text="Not Found")

        response = provider.chat("Hello!")
        assert "Error: LLM endpoint not found" in response

def test_ollama_provider_http_error():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=500)
    
        response = provider.chat("Hello!")
        assert "Error: LLM provider returned an HTTP error" in response
