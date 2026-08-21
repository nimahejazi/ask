import sys
import argparse
import re
import questionary
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live

try:
    from ask import __version__
except ImportError:
    __version__ = "unknown"
from ask.config import Config
from ask.provider import (
    MockProvider,
    Provider,
    OllamaProvider,
    LMStudioProvider,
    AnthropicProvider,
    ChatGPTProvider,
)
from ask.tools import parse_tool_definitions

console = Console()

def get_version() -> str:
    return __version__

def get_provider(name: str, config: Config) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        base_url = config.get("ollama_base_url", OllamaProvider.DEFAULT_BASE_URL)
        model = config.get("ollama_model", OllamaProvider.DEFAULT_MODEL)
        return OllamaProvider(base_url=base_url, model=model)
    if name == "lmstudio":
        base_url = config.get("lmStudio_base_url", LMStudioProvider.DEFAULT_BASE_URL)
        model = config.get("lmStudio_model", LMStudioProvider.DEFAULT_MODEL)
        return LMStudioProvider(base_url=base_url, model=model)
    if name == "anthropic":
        api_key = config.get("anthropic_api_key", "")
        model = config.get("anthropic_model", AnthropicProvider.DEFAULT_MODEL)
        return AnthropicProvider(model=model, api_key=api_key)
    if name == "chatgpt":
        api_key = config.get("chatgpt_api_key", "")
        model = config.get("chatgpt_model", ChatGPTProvider.DEFAULT_MODEL)
        return ChatGPTProvider(model=model, api_key=api_key)
    raise NotImplementedError(f"Provider {name} not implemented")

def extract_command(text: str) -> str:
    match = re.search(r"```(?:[a-zA-Z]*)\n([\s\S]*?)\n```", text)
    return match.group(1) if match else text

def handle_response(response: dict, extract_command_only: bool, already_rendered: bool = False):
    content = response.get("content", "")
    tool_calls = response.get("tool_calls", [])
    
    if tool_calls:
        return {"has_tool_calls": True, "content": content, "tool_calls": tool_calls}
    
    if extract_command_only:
        print(extract_command(content))
    elif not already_rendered:
        md = Markdown(content, style="default", justify="left")
        console.print(md)
    
    return {"has_tool_calls": False, "content": content}


def stream_response(provider: 'Provider', query: str, system_prompt: str = "", history: list = None, tools: List[Dict[str, Any]] = None):
    """Stream the response from the provider and display it in real-time with Rich Markdown."""
    full_content = ""
    
    try:
        markdown = Markdown("", style="default", justify="left")
        live = Live(markdown, console=console, refresh_per_second=20)
        live.start()
        
        for chunk in provider.chat_stream(query, system_prompt=system_prompt, history=history, tools=[]):
            if chunk:
                full_content += chunk
                new_markdown = Markdown(full_content, style="default", justify="left")
                live.update(new_markdown)
        
        live.stop()
        
        if not full_content and isinstance(provider, MockProvider):
            result = provider.chat(query, system_prompt=system_prompt, history=history, tools=tools)
            return {"content": result["content"], "tool_calls": result.get("tool_calls", [])}
    except Exception:
        pass
    
    return {"content": full_content, "tool_calls": []}

def execute_tool(tool_name: str, args: dict, tools: list) -> tuple[str, str]:
    for tool in tools:
        if tool["name"] == tool_name:
            tool_file = tool.get("_file_path")
            if not tool_file:
                return "", f"Error: No file path for tool {tool_name}"
            
            try:
                tool_path = Path(tool_file).resolve()
                if tool_path.suffix.lower() == ".py":
                    command = [sys.executable, str(tool_path)]
                elif tool_path.suffix.lower() == ".ts":
                    command = ["node", str(tool_path)]
                else:
                    command = [str(tool_path)]
                command.append(json.dumps(args))
                result = subprocess.run(
                    command,
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
    parser.add_argument('-v', '--version', action='store_true', help='Show version and exit')
    parser.add_argument('-c', '--command', action='store_true', help='Extract only executable command blocks')
    parser.add_argument('--it', action='store_true', help='Start an interactive chat session')
    parser.add_argument('-t', '--tools', type=str, help='Load tool definitions from a script file')
    parser.add_argument('-M', '--config-model', action='store_true', help='Reconfigure provider and model settings')
    parser.add_argument('-S', '--show-config', action='store_true', help='Show current configuration')
    args = parser.parse_args()


    if args.version:
        print(get_version())
        sys.exit(0)
    config = Config()
    
    if args.config_model:
        updated = configure_provider(config)
        if updated:
            console.print("[bold green]Configuration updated![/bold green]")
        else:
            console.print("[bold yellow]Configuration unchanged.[/bold yellow]")
        sys.exit(0)
    
    if args.show_config:
        show_config(config)
        sys.exit(0)
    
    tools = []
    if args.tools:
        tools = parse_tool_definitions(args.tools)
        for i, tool in enumerate(tools):
            tools[i]["_file_path"] = args.tools

    if not config.exists():
        updated = configure_provider(config)
        if not updated:
            console.print("[bold yellow]Setup cancelled.[/bold yellow]")
            sys.exit(0)

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

    # Only stream for real providers that have actual streaming implementations
    # Real providers are OllamaProvider, LMStudioProvider, AnthropicProvider, ChatGPTProvider
    provider_name = type(provider).__name__
    can_stream = (
        hasattr(provider, 'chat_stream') 
        and callable(getattr(provider, 'chat_stream'))
        and provider_name in ('OllamaProvider', 'LMStudioProvider', 'AnthropicProvider', 'ChatGPTProvider')
    )
    
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
                
                if can_stream and not args.command and not tools:
                    stream_response(provider, user_input, system_prompt=system_prompt, history=list(messages), tools=[])
                    response_dict = {"content": "", "tool_calls": []}
                else:
                    response_dict = provider.chat(user_input, system_prompt=system_prompt, history=list(messages), tools=tools)
                
                result = handle_response(response_dict, args.command, already_rendered=can_stream and not args.command and not tools)
                
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
                        already_rendered = can_stream and not args.command and not tools
                        handle_response(final_response, args.command, already_rendered=already_rendered)
                        
                        messages.append({"role": "user", "content": tool_result_message})
                        messages.append({"role": "assistant", "content": final_response.get("content", "")})
                else:
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "assistant", "content": result["content"]})
                
                initial_query = None
            except (EOFError, KeyboardInterrupt):
                break
        return

    if can_stream and not args.command and not tools:
        stream_response(provider, query, system_prompt=system_prompt, history=None, tools=[])
        response_dict = {"content": "", "tool_calls": []}
    else:
        response_dict = provider.chat(query, system_prompt=system_prompt, tools=tools)
    
    already_rendered = can_stream and not args.command and not tools
    result = handle_response(response_dict, args.command, already_rendered=already_rendered)
    
    if result["has_tool_calls"]:
        tool_output, error = execute_tool_calls(result["tool_calls"], tools)
        
        if error:
            console.print(f"[bold red]{error}[/bold red]")
        else:
            tool_result_message = f"Tool execution results:\n{tool_output}"
            
            final_response = provider.chat(
                tool_result_message,
                system_prompt=system_prompt,
                history=[
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": result["content"]},
                ],
                tools=[]
            )
            already_rendered = can_stream and not args.command and not tools
            handle_response(final_response, args.command, already_rendered=already_rendered)


_PROVIDER_CHOICES = ["mock", "ollama", "lmstudio", "anthropic", "chatgpt"]


def _select_provider(current_provider: Optional[str] = None) -> Optional[str]:
    kwargs: Dict[str, Any] = {}
    if current_provider in _PROVIDER_CHOICES:
        kwargs["default"] = current_provider
    return questionary.select(
        "Choose a provider:",
        choices=_PROVIDER_CHOICES,
        **kwargs
    ).ask()


def _select_model(prompt: str, models: List[str], current_model: Optional[str] = None) -> Optional[str]:
    kwargs: Dict[str, Any] = {}
    if current_model and current_model in models:
        kwargs["default"] = current_model
    return questionary.select(prompt, choices=models, **kwargs).ask()


def configure_provider(config: Config) -> bool:
    """One shared provider-setup flow used by both first-run bootstrap and -M reconfigure.

    Returns True if any configuration was saved, False if cancelled at the provider prompt.

    Cancel-safe:
    - If provider prompt returns None (Ctrl+C), zero config.set calls are made.
    - If model prompt returns None, provider update still applies but model is unchanged.
    Preselects current provider/model when available.
    Warns when local model discovery fails (both entry points).
    """
    current_provider = config.get("provider", None) if config.exists() else None
    if current_provider not in _PROVIDER_CHOICES:
        current_provider = None
    provider_choice = _select_provider(current_provider)
    if provider_choice is None:
        return False
    config.set("provider", provider_choice)

    if provider_choice == "ollama":
        models = OllamaProvider.get_available_models()
        if models:
            current_model = config.get("ollama_model", None)
            model = _select_model("Choose an Ollama model:", models, current_model)
            if model is not None:
                config.set("ollama_model", model)
        else:
            console.print("[bold yellow]Could not fetch Ollama models. Please make sure Ollama is running.[/bold yellow]")
    elif provider_choice == "lmstudio":
        models = LMStudioProvider.get_available_models()
        if models:
            current_model = config.get("lmStudio_model", None)
            model = _select_model("Choose an LM Studio model:", models, current_model)
            if model is not None:
                config.set("lmStudio_model", model)
        else:
            console.print("[bold yellow]Could not fetch LM Studio models. Please make sure LM Studio is running.[/bold yellow]")
    elif provider_choice == "anthropic":
        print("Please configure your Anthropic API key:")
        try:
            api_key = input("API Key: ")
        except (EOFError, KeyboardInterrupt):
            return True
        config.set("anthropic_api_key", api_key)
    elif provider_choice == "chatgpt":
        print("Please configure your ChatGPT API key:")
        try:
            api_key = input("API Key: ")
        except (EOFError, KeyboardInterrupt):
            return True
        config.set("chatgpt_api_key", api_key)
    return True


def reconfigure_provider(config: Config) -> bool:
    """Backward-compatible wrapper for the shared flow."""
    return configure_provider(config)


def show_config(config: Config):
    if not config.exists():
        console.print("[bold yellow]No configuration found.[/bold yellow]")
        console.print("Run [bold cyan]ask[/bold cyan] without arguments to configure.")
        return
    
    provider = config.get("provider", "mock")
    console.print(f"Current provider: [bold]{provider}[/bold]")
    
    if provider == "ollama":
        model = config.get("ollama_model", OllamaProvider.DEFAULT_MODEL)
        console.print(f"Model: [bold]{model}[/bold]")
    elif provider == "lmstudio":
        model = config.get("lmStudio_model", LMStudioProvider.DEFAULT_MODEL)
        console.print(f"Model: [bold]{model}[/bold]")
    elif provider == "anthropic":
        model = config.get("anthropic_model", AnthropicProvider.DEFAULT_MODEL)
        console.print(f"Model: [bold]{model}[/bold]")
    elif provider == "chatgpt":
        model = config.get("chatgpt_model", ChatGPTProvider.DEFAULT_MODEL)
        console.print(f"Model: [bold]{model}[/bold]")
    
    console.print("\nUse [bold cyan]ask --config-model[/bold cyan] to change your configuration.")


if __name__ == "__main__":
    main()
