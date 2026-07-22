import re
from typing import TypedDict, List, Optional

class ToolDefinition(TypedDict):
    name: str
    description: str
    parameters: dict

def parse_tool_definitions(file_path: str) -> List[ToolDefinition]:
    """
    Parses a file for # @tool: name | description | args comments.
    Example: # @tool: get_weather | Fetches weather for a city | {"city": "string"}
    """
    tools = []
    # Regex to match # @tool: name | description | parameters
    # It allows for optional spaces around the pipe separator
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
                        # Attempt to parse parameters as JSON
                        import json
                        parameters = json.loads(params_str)
                    except json.JSONDecodeError:
                        # Fallback or handle invalid JSON
                        parameters = {"error": f"Invalid parameter JSON: {params_str}"}
                        
                    tools.append({
                        "name": name,
                        "description": description,
                        "parameters": parameters
                    })
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

    return tools
