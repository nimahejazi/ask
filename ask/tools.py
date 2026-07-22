import re
import json
from typing import TypedDict, List, Optional, Dict, Any

class ToolDefinition(TypedDict):
    name: str
    description: str
    parameters: dict

def format_for_openai(tool: ToolDefinition) -> Dict[str, Any]:
    """
    Converts a ToolDefinition to the OpenAI/Ollama tool schema.
    Wraps parameters in a JSON schema object if they aren't already.
    """
    params = tool["parameters"]
    # If it doesn't look like a JSON Schema (missing 'type'), wrap it
    if not isinstance(params, dict) or "type" not in params:
        params = {
            "type": "object",
            "properties": params if isinstance(params, dict) else {},
            "required": []
        }

    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": params
        }
    }

def parse_tool_definitions(file_path: str) -> List[ToolDefinition]:
    """
    Parses a file for # @tool: name | description | args comments.
    Example: # @tool: get_weather | Fetches weather for a city | {"city": "string"}
    """
    tools = []
    # Regex to match # @tool: name | description | parameters
    pattern = re.compile(r"#\s*@tool:\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.*)")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    name = match.group(1).strip()
                    description = match.group(2).strip()
                    params_str = match.group(3).strip()
                    
                    try:
                        parameters = json.loads(params_str)
                    except json.JSONDecodeError:
                        parameters = {"error": f"Invalid parameter JSON: {params_str}"}
                        
                    tools.append({
                        "name": name,
                        "description": description,
                        "parameters": parameters
                    })
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

    return tools
