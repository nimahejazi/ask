import pytest
from ask.tools import parse_tool_definitions
import os

def test_parse_tool_definitions():
    # Create a temporary tool file
    tool_file = "test_tools.py"
    with open(tool_file, "w") as f:
        f.write("# @tool: get_weather | Gets weather for a city | {\"city\": \"string\"}\n")
        f.write("def get_weather(city): pass\n")
        f.write("# @tool: calculate_sum | Adds two numbers | {\"a\": \"number\", \"b\": \"number\"}\n")
        f.write("def calculate_sum(a, b): return a + b\n")
        f.write("# Not a tool comment\n")
        f.write("# @tool: invalid_json | Bad JSON | {invalid}\n")

    try:
        tools = parse_tool_definitions(tool_file)
        
        assert len(tools) == 3
        assert tools[0]["name"] == "get_weather"
        assert tools[0]["description"] == "Gets weather for a city"
        assert tools[0]["parameters"] == {"city": "string"}
        
        assert tools[1]["name"] == "calculate_sum"
        assert tools[1]["parameters"] == {"a": "number", "b": "number"}
        
        assert tools[2]["name"] == "invalid_json"
        assert "error" in tools[2]["parameters"]
    finally:
        os.remove(tool_file)

def test_parse_tool_definitions_missing_file():
    tools = parse_tool_definitions("non_existent_file.py")
    assert tools == []
