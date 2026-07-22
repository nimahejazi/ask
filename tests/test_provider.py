import pytest
import requests_mock
from ask.provider import OllamaProvider, MockProvider
from unittest.mock import patch

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
        
        assert isinstance(response, dict)
        assert response["content"] == expected_response
        assert response["tool_calls"] == []
        assert m.called

def test_ollama_provider_with_tool_calls():
    base_url = "http://test-ollama:11434"
    model = "test-model"
    provider = OllamaProvider(base_url=base_url, model=model)
    
    with patch.object(OllamaProvider, 'supports_tools', return_value=True):
        with requests_mock.Mocker() as m:
            def stream_callback(request, context):
                # Simulate streaming response - each line is a JSON object
                chunk1 = '{"model": "test", "message": {"role": "assistant", "content": "I"}, "done": false}'
                chunk2 = '{"model": "test", "message": {"role": "assistant", "tool_calls": [{"name": "get_weather", "arguments": {"city": "New York"}}]}, "done": true}'
                return chunk1 + "\n" + chunk2
            
            m.post(f"{base_url}/api/chat", text=stream_callback)

            response = provider.chat("What's the weather?")
            
            assert isinstance(response, dict)
            assert len(response["tool_calls"]) == 1

def test_ollama_provider_model_not_found():
    base_url = "http://test-ollama:11434"
    model = "missing-model"
    provider = OllamaProvider(base_url=base_url, model=model)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=404, json={"error": f"model '{model}' not found"})

        response = provider.chat("Hello!")
        assert isinstance(response, dict)
        assert f"Error: Model '{model}' not found" in response["content"]

def test_ollama_provider_endpoint_not_found():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=404, text="Not Found")

        response = provider.chat("Hello!")
        assert isinstance(response, dict)
        assert "Error: LLM endpoint not found" in response["content"]

def test_ollama_provider_http_error():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=500)
    
        response = provider.chat("Hello!")
        assert isinstance(response, dict)
        assert "Error: LLM provider returned an HTTP error" in response["content"]

def test_mock_provider():
    provider = MockProvider()
    
    response = provider.chat("Test query")
    
    assert isinstance(response, dict)
    assert "content" in response
    assert "tool_calls" in response
