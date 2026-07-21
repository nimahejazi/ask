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
        assert m.request_history[0].json()["model"] == model
        assert m.request_history[0].json()["messages"][0]["content"] == system_prompt
        assert m.request_history[0].json()["messages"][1]["content"] == query

def test_ollama_provider_http_error():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=500)

        with pytest.raises(Exception): # requests.exceptions.HTTPError
            provider.chat("Hello!")
