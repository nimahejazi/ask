import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
from pathlib import Path
import sys
from ask.cli import execute_tool_calls, handle_response

def test_handle_response_with_tool_calls():
    response = {
        "content": "I'll help you with that",
        "tool_calls": [
            {
                "name": "get_weather",
                "arguments": {"city": "New York"}
            }
        ]
    }
    
    result = handle_response(response, False)
    
    assert result["has_tool_calls"] is True
    assert result["content"] == "I'll help you with that"
    assert len(result["tool_calls"]) == 1

def test_handle_response_without_tool_calls():
    response = {
        "content": "Here is your answer",
        "tool_calls": []
    }
    
    result = handle_response(response, False)
    
    assert result["has_tool_calls"] is False
    assert result["content"] == "Here is your answer"

@patch('ask.cli.subprocess.run')
def test_execute_tool_calls_success(mock_run):
    tool_calls = [
        {
            "name": "get_weather",
            "arguments": {"city": "New York"}
        }
    ]
    
    tools = [
        {
            "name": "get_weather",
            "_file_path": "/path/to/tool"
        }
    ]
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"temp": 72}\n'
    mock_run.return_value = mock_result
    
    output, error = execute_tool_calls(tool_calls, tools)
    
    assert error == ""
    assert "Tool get_weather executed successfully" in output
    mock_run.assert_called_once()


@patch('ask.cli.subprocess.run')
def test_execute_tool_calls_resolves_relative_script_path(mock_run):
    mock_result = MagicMock(returncode=0, stdout='{"temp": 72}\n')
    mock_run.return_value = mock_result

    output, error = execute_tool_calls(
        [{"name": "get_weather", "arguments": {"city": "Paris"}}],
        [{"name": "get_weather", "_file_path": "test_sample_tool.py"}],
    )

    assert error == ""
    assert "get_weather" in output
    assert mock_run.call_args.args[0][:2] == [
        sys.executable,
        str(Path("test_sample_tool.py").resolve()),
    ]


@patch('ask.cli.subprocess.run')
def test_execute_tool_calls_runs_typescript_with_node(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout='{"temp": 72}\n')

    output, error = execute_tool_calls(
        [{"name": "get_weather", "arguments": {"city": "Paris"}}],
        [{"name": "get_weather", "_file_path": "weather.ts"}],
    )

    assert error == ""
    assert "get_weather" in output
    assert mock_run.call_args.args[0][:2] == [
        "node",
        str(Path("weather.ts").resolve()),
    ]

@patch('ask.cli.subprocess.run')
def test_execute_tool_calls_failure(mock_run):
    tool_calls = [
        {
            "name": "get_weather",
            "arguments": {"city": "New York"}
        }
    ]
    
    tools = [
        {
            "name": "get_weather",
            "_file_path": "/path/to/tool"
        }
    ]
    
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = 'Tool failed'
    mock_run.return_value = mock_result
    
    output, error = execute_tool_calls(tool_calls, tools)
    
    assert "Error executing tool get_weather" in error

def test_execute_tool_calls_unknown_tool():
    tool_calls = [
        {
            "name": "unknown_tool",
            "arguments": {}
        }
    ]
    
    tools = [
        {
            "name": "get_weather",
            "_file_path": "/path/to/tool"
        }
    ]
    
    output, error = execute_tool_calls(tool_calls, tools)
    
    assert "Unknown tool unknown_tool" in error

@patch('ask.cli.subprocess.run')
def test_execute_tool_calls_multiple(mock_run):
    tool_calls = [
        {
            "name": "tool1",
            "arguments": {"a": 1}
        },
        {
            "name": "tool2",
            "arguments": {"b": 2}
        }
    ]
    
    tools = [
        {
            "name": "tool1",
            "_file_path": "/path/to/tool1"
        },
        {
            "name": "tool2",
            "_file_path": "/path/to/tool2"
        }
    ]
    
    def side_effect(args, **kwargs):
        result = MagicMock()
        if 'tool1' in args[0]:
            result.returncode = 0
            result.stdout = '{"result": 1}\n'
        else:
            result.returncode = 0
            result.stdout = '{"result": 2}\n'
        return result
    
    mock_run.side_effect = side_effect
    
    output, error = execute_tool_calls(tool_calls, tools)
    
    assert error == ""
    assert "tool1" in output
    assert "tool2" in output
