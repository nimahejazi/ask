import sys
import argparse
import re
import questionary
import subprocess
import json
from rich.console import Console
from rich.markdown import Markdown
from ask.config import Config
from ask.provider import MockProvider, Provider, OllamaProvider, LMStudioProvider
from ask.tools import parse_tool_definitions

console = Console()

def get_provider(name: str, config: Config) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        base_url = config.get("ollama_base_url", OllamaProvider.DEFAULT_BASE_URL)
        model = config.get("ollama_model", OllamaProvider.DEFAULT_MODEL)
        return OllamaProvider(base_url=base_url, model=model)
    if name == "lmstudio":
        base_url = config.get("lmstudio_base_url", LMStudioProvider.DEFAULT_BASE_URL)
        model = config.get("lmstudio_model", LMStudioProvider.DEFAULT_MODEL)
        return LMStudioProvider(base_url=base_url, model=model)
    raise NotImplementedError(f"Provider {name} not implemented")

def extract_command(text: str) -> str:
    match = re.search(r"```(?:[a-zA-Z]*)\n([\s\S]*?)\n```", text)
    return match.group(1) if match else text

def handle_response(response: dict, extract_command_only: bool):
    content = response.get("content", "")
    tool_calls = response.get("tool_calls", [])
    
    if tool_calls:
        return {"has_tool_calls": True, "content": content, "tool_calls": tool_calls}
    
    if extract_command_only:
        print(extract_command(content))
    else:
        console.print(Markdown(content))
    
    return {"has_tool_calls": False, "content": content}

def execute_tool(tool_name: str, args: dict, tools: list) -> tuple[str, str]:
    for tool in tools:
        if tool["name"] == tool_name:
            tool_file = tool.get("_file_path")
            if not tool_file:
                return "", f"Error: No file path for tool {tool_name}"
            
            try:
                result = subprocess.run(
                    [tool_file, json.dumps(args)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return result.stdout.strip(), ""
                else:
                    return "", f"Error executing tool {tool_name}: {result.stderr.strip()}"
            except subprocess.TimeoutExpired:
                return "", f"Error: Tool execution timed out for {tool_name}"
            except Exception as e:
                return "", f"Error executing tool {tool_name}: {str(e)}"
    
    return "", f"Error: Unknown tool {tool_name}"

def execute_tool_calls(tool_calls: list, tools: list) -> tuple[str, str]:
    results = []
    for call in tool_calls:
        tool_name = call.get("name", "")
        args = call.get("arguments", {})
        
        output, error = execute_tool(tool_name, args, tools)
        if error:
            return "", error
        
        results.append(f"Tool {tool_name} executed successfully. Output: {output}")
    
    return "\n".join(results), ""

def main():
    parser = argparse.ArgumentParser(description='ask - AI CLI')
    parser.add_argument('query', nargs='*', help='Your query to the AI')
    parser.add_argument('-c', '--command', action='store_true', help='Extract only executable command blocks')
    parser.add_argument('--it', action='store_true', help='Start an interactive chat session')
    parser.add_argument('-t', '--tools', type=str, help='Load tool definitions from a script file')
    args = parser.parse_args()

    config = Config()
    
    tools = []
    if args.tools:
        tools = parse_tool_definitions(args.tools)
        for i, tool in enumerate(tools):
            tools[i]["_file_path"] = args.tools

    if not config.exists():
        provider_choice = questionary.select(
            "Choose a provider:",
            choices=["mock", "ollama", "lmstudio"]
        ).ask()
        
        config.set("provider", provider_choice)

        if provider_choice == "ollama":
            models = OllamaProvider.get_available_models()
            if models:
                model = questionary.select(
                    "Choose an Ollama model:",
                    choices=models
                ).ask()
                config.set("ollama_model", model)
        elif provider_choice == "lmstudio":
            models = LMStudioProvider.get_available_models()
            if models:
                model = questionary.select(
                    "Choose an LM Studio model:",
                    choices=models
                ).ask()
                config.set("lmstudio_model", model)

    query = " ".join(args.query) if args.query else None
    if not query and not args.it:
        parser.print_help()
        sys.exit(1)

    provider_name = config.get("provider", "mock")
    try:
        provider = get_provider(provider_name, config)
    except NotImplementedError as e:
        print(e)
        sys.exit(1)

    system_prompt = config.get("system_prompt", "")

    if args.it:
        messages = []
        initial_query = " ".join(args.query) if args.query else None
        
        while True:
            try:
                user_input = initial_query if initial_query else input("> ")
                if not user_input or not user_input.strip():
                    if initial_query is not None: 
                        initial_query = None
                    continue

                if user_input.lower() == "exit":
                    break
                
                response_dict = provider.chat(user_input, system_prompt=system_prompt, history=list(messages), tools=tools)
                result = handle_response(response_dict, args.command)
                
                if result["has_tool_calls"]:
                    tool_output, error = execute_tool_calls(result["tool_calls"], tools)
                    
                    if error:
                        console.print(f"[bold red]{error}[/bold red]")
                        messages.append({"role": "user", "content": user_input})
                        messages.append({"role": "assistant", "content": error})
                    else:
                        tool_result_message = f"Tool execution results:\n{tool_output}"
                        messages.append({"role": "user", "content": user_input})
                        messages.append({"role": "assistant", "content": result["content"]})
                        
                        final_response = provider.chat(
                            tool_result_message,
                            system_prompt=system_prompt,
                            history=list(messages),
                            tools=[]
                        )
                        handle_response(final_response, args.command)
                        
                        messages.append({"role": "user", "content": tool_result_message})
                        messages.append({"role": "assistant", "content": final_response.get("content", "")})
                else:
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "assistant", "content": result["content"]})
                
                initial_query = None
            except (EOFError, KeyboardInterrupt):
                break
        return

    response_dict = provider.chat(query, system_prompt=system_prompt, tools=tools)
    result = handle_response(response_dict, args.command)
    
    if result["has_tool_calls"]:
        tool_output, error = execute_tool_calls(result["tool_calls"], tools)
        
        if error:
            console.print(f"[bold red]{error}[/bold red]")
        else:
            tool_result_message = f"Tool execution results:\n{tool_output}"
            
            final_response = provider.chat(
                tool_result_message,
                system_prompt=system_prompt,
                history=[],
                tools=[]
            )
            handle_response(final_response, args.command)

if __name__ == "__main__":
    main()
