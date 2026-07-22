import pytest
from unittest.mock import patch, MagicMock
from ask.provider import OllamaProvider, LMStudioProvider

@pytest.fixture
def ollama_provider():
    return OllamaProvider(base_url="http://test:11434", model="test-model")

@pytest.fixture
def lmstudio_provider():
    return LMStudioProvider(base_url="http://test:1234", model="test-model")

def test_ollama_provider_empty_tool_calls_response(ollama_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Here is the answer"
            }
        }
        mock_post.return_value = mock_response
        
        response = ollama_provider.chat("test")
        
        assert isinstance(response, dict)
        assert response["tool_calls"] == []

def test_lmstudio_provider_empty_tool_calls_response(lmstudio_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Here is the answer"
                }
            }]
        }
        mock_post.return_value = mock_response
        
        response = lmstudio_provider.chat("test")
        
        assert isinstance(response, dict)
        assert response["tool_calls"] == []

def test_ollama_provider_connection_error(ollama_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_post.side_effect = Exception("Connection refused")
        
        response = ollama_provider.chat("test")
        
        assert isinstance(response, dict)
        assert "unexpected error" in response["content"].lower()

def test_lmstudio_provider_connection_error(lmstudio_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_post.side_effect = Exception("Connection refused")
        
        response = lmstudio_provider.chat("test")
        
        assert isinstance(response, dict)
        assert "Error" in response["content"]

def test_lmstudio_provider_empty_choices(lmstudio_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{}]}
        mock_post.return_value = mock_response
        
        response = lmstudio_provider.chat("test")
        
        assert isinstance(response, dict)
        assert response["content"] == ""

def test_ollama_provider_missing_message(ollama_provider):
    with patch('ask.provider.requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        
        response = ollama_provider.chat("test")
        
        assert isinstance(response, dict)
        assert response["content"] == ""