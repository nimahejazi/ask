import sys
import os
import argparse
import re
import getpass
import questionary
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    _has_prompt_toolkit = True
except ImportError:
    PromptSession = None  # type: ignore
    InMemoryHistory = None  # type: ignore
    _has_prompt_toolkit = False

try:
    from ask import __version__
except ImportError:
    __version__ = "unknown"
from ask.config import Config
from ask.provider import (
    MockProvider,
    Provider,
    ProviderError,
    OllamaProvider,
    LMStudioProvider,
    AnthropicProvider,
    ChatGPTProvider,
)
from ask.tools import parse_tool_definitions

console = Console()

def get_version() -> str:
    return __version__

def _resolve_api_key(config: Config, config_key: str, env_var: str) -> str:
    """Precedence: stored config wins; env var used only when config has none."""
    stored = config.get(config_key, "")
    if stored:
        return stored
    return os.getenv(env_var, "")

def get_provider(name: str, config: Config) -> Provider:
    max_tokens = config.get("max_tokens", None)
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        base_url = config.get("ollama_base_url", OllamaProvider.DEFAULT_BASE_URL)
        model = config.get("ollama_model", OllamaProvider.DEFAULT_MODEL)
        return OllamaProvider(base_url=base_url, model=model, max_tokens=max_tokens)
    if name == "lmstudio":
        base_url = config.get("lmStudio_base_url", LMStudioProvider.DEFAULT_BASE_URL)
        model = config.get("lmStudio_model", LMStudioProvider.DEFAULT_MODEL)
        return LMStudioProvider(base_url=base_url, model=model, max_tokens=max_tokens)
    if name == "anthropic":
        api_key = _resolve_api_key(config, "anthropic_api_key", "ANTHROPIC_API_KEY")
        model = config.get("anthropic_model", AnthropicProvider.DEFAULT_MODEL)
        return AnthropicProvider(model=model, api_key=api_key, max_tokens=max_tokens)
    if name == "chatgpt":
        api_key = _resolve_api_key(config, "chatgpt_api_key", "OPENAI_API_KEY")
        model = config.get("chatgpt_model", ChatGPTProvider.DEFAULT_MODEL)
        return ChatGPTProvider(model=model, api_key=api_key, max_tokens=max_tokens)
    raise NotImplementedError(f"Provider {name} not implemented")

def extract_command(text: str) -> str:
    match = re.search(r"```(?:[a-zA-Z]*)\n([\s\S]*?)\n```", text)
    return match.group(1) if match else text

def is_error_content(content: str) -> bool:
    return isinstance(content, str) and content.startswith("Error:")


def handle_response(response: dict, extract_command_only: bool, already_rendered: bool = False):
    content = response.get("content", "")
    tool_calls = response.get("tool_calls", [])

    if is_error_content(content):
        # Do not treat error as command; caller should handle stderr and exit
        print(content, file=sys.stderr)
        return {"has_tool_calls": False, "content": content, "is_error": True}

    if tool_calls:
        return {"has_tool_calls": True, "content": content, "tool_calls": tool_calls}
    
    if extract_command_only:
        # Do not print error text as command (already handled above)
        print(extract_command(content))
    elif not already_rendered:
        md = Markdown(content, style="default", justify="left")
        console.print(md)
    
    return {"has_tool_calls": False, "content": content}


def stream_response(provider: 'Provider', query: str, system_prompt: str = "", history: list = None, tools: List[Dict[str, Any]] = None):
    """Stream the response from the provider and display it in real-time with Rich Markdown.
    Returns dict with content and tool_calls. Raises ProviderError on failure.
    """
    full_content = ""

    markdown = Markdown("", style="default", justify="left")
    live = Live(markdown, console=console, refresh_per_second=20)
    live.start()
    try:
        for chunk in provider.chat_stream(query, system_prompt=system_prompt, history=history, tools=[]):
            if chunk:
                full_content += chunk
                new_markdown = Markdown(full_content, style="default", justify="left")
                live.update(new_markdown)
    finally:
        live.stop()

    if not full_content and isinstance(provider, MockProvider):
        result = provider.chat(query, system_prompt=system_prompt, history=history, tools=tools)
        return {"content": result["content"], "tool_calls": result.get("tool_calls", [])}

    return {"content": full_content, "tool_calls": []}

def _confirm_tool_execution(tool_name: str, args: dict, auto_confirm: bool = False) -> bool:
    if auto_confirm:
        return True
    # Non-interactive stdin: treat as decline unless -y
    if not sys.stdin.isatty():
        print(f"Tool '{tool_name}' with arguments {json.dumps(args)} requires confirmation — skipping (use -y to auto-confirm).", file=sys.stderr)
        return False
    try:
        answer = input(f"Execute tool '{tool_name}' with arguments {json.dumps(args)}? [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False

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

def execute_tool_calls(tool_calls: list, tools: list, auto_confirm: bool = False) -> tuple[str, str]:
    results = []
    for call in tool_calls:
        tool_name = call.get("name", "")
        args = call.get("arguments", {})

        if not _confirm_tool_execution(tool_name, args, auto_confirm=auto_confirm):
            # Graceful decline: feed back to model without crashing
            results.append(f"Tool {tool_name} execution declined by user.")
            continue
        
        output, error = execute_tool(tool_name, args, tools)
        if error:
            return "", error
        
        results.append(f"Tool {tool_name} executed successfully. Output: {output}")
    
    return "\n".join(results), ""


def _build_tool_result_messages(tool_calls: list, tools: list, auto_confirm: bool = False) -> list[dict]:
    """Build native tool result messages with ids, handling confirmation and errors as tool results."""
    results: list[dict] = []
    for idx, call in enumerate(tool_calls):
        tool_name = call.get("name", "")
        args = call.get("arguments", {})
        call_id = call.get("id") or f"call_{idx}_{tool_name}"
        if not _confirm_tool_execution(tool_name, args, auto_confirm=auto_confirm):
            results.append({"role": "tool", "tool_call_id": call_id, "content": f"Tool {tool_name} execution declined by user."})
            continue
        output, error = execute_tool(tool_name, args, tools)
        if error:
            # Feed error back as tool result instead of aborting
            results.append({"role": "tool", "tool_call_id": call_id, "content": error})
        else:
            # For native protocol, just the output (provider will format)
            results.append({"role": "tool", "tool_call_id": call_id, "content": output if output else "Tool executed successfully with no output."})
    return results


def _run_tool_loop(provider: Provider, history: list[dict], tools: list, system_prompt: str, auto_confirm: bool, initial_response: dict, max_rounds: int = 5) -> dict:
    """Run multi-round tool loop until model answers without tool calls or cap reached.
    History is mutated in place (assistant tool calls and tool results appended).
    Returns final response dict (without tool calls).
    """
    response = initial_response
    for round_idx in range(max_rounds):
        if not response.get("tool_calls"):
            return response
        # Preserve assistant tool-call turn verbatim
        history.append({"role": "assistant", "content": response.get("content", ""), "tool_calls": response.get("tool_calls", [])})
        # Build and append native tool result messages
        tool_results = _build_tool_result_messages(response.get("tool_calls", []), tools, auto_confirm=auto_confirm)
        history.extend(tool_results)
        # Call provider again with updated history; no new user query
        try:
            next_response = provider.chat("", system_prompt=system_prompt, history=list(history), tools=tools)
        except ProviderError as e:
            print(str(e), file=sys.stderr)
            return {"content": str(e), "tool_calls": [], "is_error": True}
        if is_error_content(next_response.get("content", "")):
            print(next_response["content"], file=sys.stderr)
            return next_response
        response = next_response
        if not response.get("tool_calls"):
            return response
    # Cap reached
    print(f"Warning: Tool call loop exceeded {max_rounds} rounds — stopping.", file=sys.stderr)
    return response

def main():
    parser = argparse.ArgumentParser(description='ask - AI CLI')
    parser.add_argument('query', nargs='*', help='Your query to the AI')
    parser.add_argument('-v', '--version', action='store_true', help='Show version and exit')
    parser.add_argument('-c', '--command', action='store_true', help='Extract only executable command blocks')
    parser.add_argument('--it', action='store_true', help='Start an interactive chat session')
    parser.add_argument('-t', '--tools', type=str, help='Load tool definitions from a script file')
    parser.add_argument('-M', '--config-model', action='store_true', help='Reconfigure provider and model settings')
    parser.add_argument('-S', '--show-config', action='store_true', help='Show current configuration')
    parser.add_argument('-y', '--yes', action='store_true', help='Auto-confirm tool execution without prompting')
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
        session = None
        if _has_prompt_toolkit and sys.stdin.isatty() and sys.stdout.isatty():
            try:
                session = PromptSession(history=InMemoryHistory())
            except Exception:
                session = None
        
        while True:
            try:
                if initial_query is not None:
                    user_input = initial_query
                elif session is not None:
                    try:
                        user_input = session.prompt("> ")
                    except KeyboardInterrupt:
                        # Ctrl-C mid-input clears the line without exiting
                        continue
                    except EOFError:
                        break
                else:
                    user_input = input("> ")
                if not user_input or not user_input.strip():
                    if initial_query is not None: 
                        initial_query = None
                    continue

                if user_input.lower() == "exit":
                    break
                
                try:
                    if can_stream and not args.command and not tools:
                        response_dict = stream_response(provider, user_input, system_prompt=system_prompt, history=list(messages), tools=[])
                    else:
                        response_dict = provider.chat(user_input, system_prompt=system_prompt, history=list(messages), tools=tools)
                except ProviderError as e:
                    print(str(e), file=sys.stderr)
                    # In interactive mode, show error but keep session alive
                    continue
                except Exception as e:
                    print(f"Error: {e}", file=sys.stderr)
                    continue

                if is_error_content(response_dict.get("content", "")):
                    print(response_dict["content"], file=sys.stderr)
                    continue
                
                result = handle_response(response_dict, args.command, already_rendered=can_stream and not args.command and not tools)
                if result.get("is_error"):
                    continue
                
                if result["has_tool_calls"]:
                    # Native tool-result protocol: preserve assistant turn verbatim, send tool results with ids, loop
                    messages.append({"role": "user", "content": user_input})
                    # Copy history for loop (messages will be mutated)
                    loop_history = list(messages)
                    final_response = _run_tool_loop(provider, loop_history, tools, system_prompt, args.yes, initial_response=response_dict, max_rounds=5)
                    # Sync history back
                    messages.clear()
                    messages.extend(loop_history)
                    if final_response.get("is_error") or is_error_content(final_response.get("content", "")):
                        continue
                    handle_response(final_response, args.command, already_rendered=False)
                    messages.append({"role": "assistant", "content": final_response.get("content", "")})
                else:
                    messages.append({"role": "user", "content": user_input})
                    messages.append({"role": "assistant", "content": result["content"]})
                
                initial_query = None
            except (EOFError, KeyboardInterrupt):
                break
        return

    # Single-query (non-interactive) path
    try:
        if can_stream and not args.command and not tools:
            response_dict = stream_response(provider, query, system_prompt=system_prompt, history=None, tools=[])
        else:
            response_dict = provider.chat(query, system_prompt=system_prompt, tools=tools)
    except ProviderError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if is_error_content(response_dict.get("content", "")):
        print(response_dict["content"], file=sys.stderr)
        sys.exit(1)

    already_rendered = can_stream and not args.command and not tools
    result = handle_response(response_dict, args.command, already_rendered=already_rendered)
    if result.get("is_error"):
        sys.exit(1)
    
    if result["has_tool_calls"]:
        # Native protocol loop
        history = [
            {"role": "user", "content": query},
        ]
        final_response = _run_tool_loop(provider, history, tools, system_prompt, args.yes, initial_response=response_dict, max_rounds=5)
        if final_response.get("is_error") or is_error_content(final_response.get("content", "")):
            sys.exit(1)
        handle_response(final_response, args.command, already_rendered=False)


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
        env_key = os.getenv("ANTHROPIC_API_KEY", "")
        stored = config.get("anthropic_api_key", "")
        if env_key and not stored:
            console.print("[dim]Using API key from ANTHROPIC_API_KEY environment variable (not stored in config).[/dim]")
        else:
            print("Please configure your Anthropic API key:")
            try:
                try:
                    api_key = getpass.getpass("API Key: ")
                except Exception:
                    api_key = input("API Key: ")
            except (EOFError, KeyboardInterrupt):
                return True
            config.set("anthropic_api_key", api_key)
    elif provider_choice == "chatgpt":
        env_key = os.getenv("OPENAI_API_KEY", "")
        stored = config.get("chatgpt_api_key", "")
        if env_key and not stored:
            console.print("[dim]Using API key from OPENAI_API_KEY environment variable (not stored in config).[/dim]")
        else:
            print("Please configure your ChatGPT API key:")
            try:
                try:
                    api_key = getpass.getpass("API Key: ")
                except Exception:
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

    # Show API key status (never the value)
    if provider == "anthropic":
        has_config = bool(config.get("anthropic_api_key", ""))
        has_env = bool(os.getenv("ANTHROPIC_API_KEY", ""))
        if has_config:
            console.print("API key: [bold]set[/bold] (stored in config)")
        elif has_env:
            console.print("API key: [bold]set[/bold] (from ANTHROPIC_API_KEY)")
        else:
            console.print("API key: [bold yellow]not set[/bold yellow]")
    elif provider == "chatgpt":
        has_config = bool(config.get("chatgpt_api_key", ""))
        has_env = bool(os.getenv("OPENAI_API_KEY", ""))
        if has_config:
            console.print("API key: [bold]set[/bold] (stored in config)")
        elif has_env:
            console.print("API key: [bold]set[/bold] (from OPENAI_API_KEY)")
        else:
            console.print("API key: [bold yellow]not set[/bold yellow]")
    
    # Show max_tokens
    from ask.provider import resolve_max_tokens, effective_max_tokens_for_anthropic
    raw_max = config.get("max_tokens", None)
    if raw_max is None:
        # Anthropic default is 1024, others unset
        if provider == "anthropic":
            console.print(f"max_tokens: [bold]1024[/bold] (default)")
        else:
            console.print(f"max_tokens: [bold]not set[/bold] (provider default)")
    else:
        validated = resolve_max_tokens(raw_max, warn=False)
        if validated is None:
            # invalid, show raw and effective
            effective = effective_max_tokens_for_anthropic(raw_max, warn=False) if provider == "anthropic" else "default"
            console.print(f"max_tokens: [bold]{raw_max}[/bold] (invalid, using {effective})")
        else:
            console.print(f"max_tokens: [bold]{validated}[/bold]")
    
    console.print("\nUse [bold cyan]ask --config-model[/bold cyan] to change your configuration.")


if __name__ == "__main__":
    main()
