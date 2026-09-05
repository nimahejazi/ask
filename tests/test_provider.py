import json
import pytest
import requests_mock
from ask.provider import LMStudioProvider, OllamaProvider, MockProvider
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


def test_ollama_provider_normalizes_native_tool_calls():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url, model="test-model")

    with patch.object(OllamaProvider, "supports_tools", return_value=True):
        with requests_mock.Mocker() as m:
            m.post(f"{base_url}/api/chat", json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call-1",
                        "function": {
                            "name": "get_weather",
                            "arguments": {"city": "Paris"},
                        },
                    }],
                },
                "done": True,
            })

            response = provider.chat(
                "What's the weather?",
                tools=[{
                    "name": "get_weather",
                    "description": "Gets weather for a city",
                    "parameters": {"city": "string"},
                }],
            )

    assert response["tool_calls"] == [{
        "name": "get_weather",
        "arguments": {"city": "Paris"},
        "id": "call-1",
    }]


def test_ollama_provider_rejects_invalid_tool_arguments():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url, model="test-model")

    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", json={
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "get_weather",
                        "arguments": "{not valid json",
                    },
                }],
            },
            "done": True,
        })

        response = provider.chat("What's the weather?")

    assert response["tool_calls"] == []
    assert "invalid tool call arguments" in response["content"].lower()

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
        assert "Not Found" in response["content"]


def test_ollama_provider_does_not_misclassify_route_not_found_as_model_error():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url, model="test-model")

    with requests_mock.Mocker() as m:
        m.post(
            f"{base_url}/api/chat",
            status_code=404,
            json={"error": "route not found"},
        )

        response = provider.chat("Hello!")

    assert "endpoint not found" in response["content"].lower()
    assert "route not found" in response["content"]

def test_ollama_provider_http_error():
    base_url = "http://test-ollama:11434"
    provider = OllamaProvider(base_url=base_url)
    
    with requests_mock.Mocker() as m:
        m.post(
            f"{base_url}/api/chat",
            status_code=500,
            json={"error": "provider exploded"},
        )
    
        response = provider.chat("Hello!")
        assert isinstance(response, dict)
        assert "Error: LLM provider returned an HTTP error" in response["content"]
        assert "provider exploded" in response["content"]

def test_mock_provider():
    provider = MockProvider()
    
    response = provider.chat("Test query")
    
    assert isinstance(response, dict)
    assert "content" in response
    assert "tool_calls" in response


def test_ollama_tool_support_probe_fails_closed():
    base_url = "http://test-ollama:11434"

    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/api/chat", status_code=500)

        assert OllamaProvider.supports_tools(base_url, "test-model") is False


def test_lmstudio_tool_support_probe_fails_closed():
    base_url = "http://test-lmstudio:1234"

    with requests_mock.Mocker() as m:
        m.post(f"{base_url}/v1/chat/completions", status_code=500)

        assert LMStudioProvider.supports_tools(base_url, "test-model") is False


@patch('ask.provider.requests.post', side_effect=ConnectionError)
def test_tool_support_probe_connection_error_fails_closed(mock_post):
    assert OllamaProvider.supports_tools("http://unavailable", "test-model") is False
    assert LMStudioProvider.supports_tools("http://unavailable", "test-model") is False


def test_ollama_provider_sends_history_tool_calls_as_objects():
    """Ollama /api/chat requires tool_calls[].function.arguments as an object.
    OpenAI-style string arguments in history trigger:
    "Value looks like object, but can't find closing '}' symbol"."""
    from ask.provider import _build_openai_messages

    history = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_0_search_notes",
                "name": "search_notes",
                "arguments": {"query": "deploy"},
            }],
        },
        {"role": "tool", "tool_call_id": "call_0_search_notes", "content": "{}"},
    ]

    with requests_mock.Mocker() as m:
        m.post("http://test-ollama:11434/api/chat", json={"message": {"role": "assistant", "content": "ok"}, "done": True})
        OllamaProvider(base_url="http://test-ollama:11434", model="test-model").chat(
            "", history=list(history), tools=[]
        )
        sent = m.last_request.json()

    assistant_msg = [msg for msg in sent["messages"] if msg["role"] == "assistant" and msg.get("tool_calls")][0]
    args = assistant_msg["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, dict), f"Ollama got string arguments: {args!r}"


def test_openai_builder_keeps_string_arguments_for_openai_wire_format():
    """LM Studio / ChatGPT expect arguments as a JSON string — unchanged."""
    from ask.provider import _build_openai_messages

    messages = _build_openai_messages("", [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "name": "search_notes", "arguments": {"query": "deploy"}}],
        },
    ], "")

    args = messages[1]["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, str)
    assert json.loads(args) == {"query": "deploy"}


def _ollama_json_response(message_body):
    return {"message": message_body, "done": True}


def test_ollama_thinking_fallback_when_content_empty():
    """Qwen3-style thinking models: answer lands in 'thinking', content empty."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model")
    with requests_mock.Mocker() as m:
        m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
            "role": "assistant", "content": "",
            "thinking": "To deploy, run kubectl first.",
        }))
        response = provider.chat("how do I deploy?")
    assert response["content"] == "To deploy, run kubectl first."
    assert response["tool_calls"] == []


def test_ollama_empty_response_becomes_error_not_silence():
    """Final response with no content, no thinking, no calls -> Error: content."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model")
    with requests_mock.Mocker() as m:
        m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
            "role": "assistant", "content": "",
        }))
        response = provider.chat("hello")
    assert response["content"].startswith("Error:")
    from ask.cli import is_error_content
    assert is_error_content(response["content"])


def test_ollama_content_preferred_over_thinking():
    """When content exists it wins; thinking is never appended."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model")
    with requests_mock.Mocker() as m:
        m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
            "role": "assistant", "content": "the answer", "thinking": "reasoning here",
        }))
        response = provider.chat("hello")
    assert response["content"] == "the answer"


def test_ollama_tool_call_round_not_affected_by_thinking_fallback():
    """Tool-call rounds keep working; thinking never overrides a tool call turn."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model")
    with patch.object(OllamaProvider, 'supports_tools', return_value=True):
        with requests_mock.Mocker() as m:
            m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
                "role": "assistant", "content": "", "thinking": "I should search",
                "tool_calls": [{"function": {"name": "search_notes", "arguments": {"query": "deploy"}}}],
            }))
            response = provider.chat("hello", tools=[{"name": "search_notes", "description": "d", "parameters": {}}])
    assert len(response["tool_calls"]) == 1
    assert response["content"] == ""


def test_ollama_think_false_sent_when_configured():
    """ollama_think=false in config -> 'think': false in payload."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model", think=False)
    with patch.object(OllamaProvider, 'supports_tools', return_value=True):
        with requests_mock.Mocker() as m:
            m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
                "role": "assistant", "content": "ok",
            }))
            provider.chat("hello", tools=[{"name": "t", "description": "d", "parameters": {}}])
            assert m.last_request.json().get("think") is False
            # Non-tool path too
            provider.chat("hello")
            assert m.last_request.json().get("think") is False


def test_ollama_think_omitted_when_unset():
    """No ollama_think config -> no 'think' key (older Ollama rejects it)."""
    provider = OllamaProvider(base_url="http://test-ollama:11434", model="test-model")
    with requests_mock.Mocker() as m:
        m.post("http://test-ollama:11434/api/chat", json=_ollama_json_response({
            "role": "assistant", "content": "ok",
        }))
        provider.chat("hello")
        assert "think" not in m.last_request.json()


def test_get_provider_reads_ollama_think():
    from ask.cli import get_provider
    class FakeConfig:
        def get(self, key, default=None):
            return {"ollama_think": False}.get(key, default)
    provider = get_provider("ollama", FakeConfig())
    assert provider.think is False
