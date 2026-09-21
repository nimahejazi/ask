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
from ask.notes import default_notes_store
from ask.notes_tools import (
    BUILT_IN_TOOL_NAMES,
    NOTES_TOOLS,
    execute_built_in_tool,
    filter_built_in_tools,
    notes_only_guidance,
    notes_system_guidance,
)

READ_ONLY_NOTE_TOOLS = ("search_notes", "read_note")
from ask.notes_index import (
    DEFAULT_EMBEDDING_MODEL,
    ollama_has_embedding_model,
    ollama_pull_embedding,
)

console = Console()


def _err_console():
    """Fresh stderr console per call so capsys/redirect capture it."""
    return Console(file=sys.stderr)

def get_version() -> str:
    return __version__


def execute_built_in_tool_with_confirmation(tool_name: str, args: dict, auto_confirm: bool = False) -> tuple[str, str]:
    """Built-in notes tools may write; route writes through confirmation like user tools."""
    if tool_name == "save_note" and not auto_confirm:
        if not sys.stdin.isatty():
            print(f"Tool '{tool_name}' with arguments {json.dumps(args)} requires confirmation — skipping (use -y to auto-confirm).", file=sys.stderr)
            return "", f"Tool {tool_name} execution declined by user."
        try:
            answer = input(f"Save note '{args.get('title', '')}'? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                return "", f"Tool {tool_name} execution declined by user."
        except (EOFError, KeyboardInterrupt):
            return "", f"Tool {tool_name} execution declined by user."
    if tool_name == "search_notes":
        with console.status("Searching notes…"):
            return execute_built_in_tool(tool_name, args)
    return execute_built_in_tool(tool_name, args)

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
        think = config.get("ollama_think", None)
        if think is not None:
            think = bool(think)
        return OllamaProvider(base_url=base_url, model=model, max_tokens=max_tokens, think=think)
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
    # Read-only built-in notes tools never prompt: AI reads freely, humans
    # gate writes (save_note) and user-provided tools.
    if auto_confirm or tool_name in READ_ONLY_NOTE_TOOLS:
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
    # Built-in Notes Tools are executed in-process, not via scripts
    if tool_name in BUILT_IN_TOOL_NAMES:
        return execute_built_in_tool_with_confirmation(tool_name, args)
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
            with console.status(" "):
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

def _find_notes_dispatch(argv: list[str]) -> Optional[int]:
    """Return index of the first positional token if it is 'notes', else None.

    Skips flags (and the value of value-taking flags) so flag order doesn't
    matter: `ask --no-notes notes list` dispatches to notes_command.
    """
    i = 0
    value_flags = {"-t", "--tools"}
    while i < len(argv):
        token = argv[i]
        if token in value_flags:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return i if token == "notes" else None
    return None


def main():
    parser = argparse.ArgumentParser(
        prog="ask",
        description='ask - AI CLI',
        epilog=(
            "notes: personal notes are consulted automatically when answering.\n"
            "  manage them with: ask notes {browse,list,show,add,edit,delete,search,reindex}\n"
            "  help: ask notes -h"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('query', nargs='*', help='Your query to the AI ("ask notes ..." manages notes)')
    parser.add_argument('-v', '--version', action='store_true', help='Show version and exit')
    parser.add_argument('-c', '--command', action='store_true', help='Extract only executable command blocks')
    parser.add_argument('--it', action='store_true', help='Start an interactive chat session')
    parser.add_argument('-t', '--tools', type=str, help='Load tool definitions from a script file')
    parser.add_argument('-M', '--config-model', action='store_true', help='Reconfigure provider and model settings')
    parser.add_argument('-S', '--show-config', action='store_true', help='Show current configuration')
    parser.add_argument('-y', '--yes', action='store_true', help='Auto-confirm tool execution without prompting')
    notes_group = parser.add_mutually_exclusive_group()
    notes_group.add_argument('-N', '--no-notes', action='store_true', help='Disable consulting personal notes for this query')
    notes_group.add_argument('-n', '--notes-only', action='store_true', help='Answer ONLY from your personal notes (requires notes to exist)')
    # `ask notes ...` must dispatch before main parsing (main's query positional
    # swallows the words, and main's -h/--help would short-circuit notes help)
    notes_idx = _find_notes_dispatch(sys.argv[1:])
    if notes_idx is not None:
        rest = sys.argv[1:][notes_idx + 1:]
        sys.exit(notes_command(rest))
    args, remaining = parser.parse_known_args()

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
        if args.notes_only:
            _err_console().print(
                "[yellow]Ignoring -t/--tools: --notes-only uses only the built-in notes tools.[/yellow]"
            )
        else:
            tools = filter_built_in_tools(parse_tool_definitions(args.tools))
            for i, tool in enumerate(tools):
                tools[i]["_file_path"] = args.tools

    if not config.exists():
        updated = configure_provider(config)
        if not updated:
            console.print("[bold yellow]Setup cancelled.[/bold yellow]")
            sys.exit(0)

    provider_name = config.get("provider", "mock")

    # Notes Tools: attached by default when notes exist and not disabled.
    # Attaching tools switches to the non-streaming path (the model may call tools).
    notes_store = default_notes_store()
    if args.notes_only:
        if not notes_store.list_notes():
            _err_console().print(
                "[red]No notes found. Create some first: ask notes add \"text\"[/red]"
            )
            sys.exit(1)
        tools = NOTES_TOOLS + tools
    else:
        attach_notes = (
            not args.no_notes
            and bool(notes_store.list_notes())
        )
        if attach_notes:
            tools = NOTES_TOOLS + tools

    query = " ".join(args.query) if args.query else None
    if not query and not args.it:
        parser.print_help()
        sys.exit(1)

    try:
        provider = get_provider(provider_name, config)
    except NotImplementedError as e:
        print(e)
        sys.exit(1)

    system_prompt = config.get("system_prompt", "")
    if args.notes_only:
        system_prompt = (system_prompt + "\n\n" + notes_only_guidance()).strip()
    elif attach_notes:
        system_prompt = (system_prompt + "\n\n" + notes_system_guidance()).strip()

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
                        with console.status(" "):
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
            with console.status(" "):
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
        _ensure_ollama_embedding_model(config, confirm=questionary.confirm)
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


def _ensure_ollama_embedding_model(config: Config, confirm=None) -> None:
    """Notes bootstrap: when configuring ollama, make sure an embedding model is
    available for semantic note search; offer to pull the default one."""
    base_url = config.get("ollama_base_url", None)
    if ollama_has_embedding_model(base_url):
        return
    if confirm is None:
        confirm = questionary.confirm
    console.print("[yellow]No embedding model found in Ollama (needed for semantic note search).[/yellow]")
    answer = confirm(
        f"Pull '{DEFAULT_EMBEDDING_MODEL}' now? (recommended, ~274MB)",
        default=True,
    )
    pull = answer.ask() if hasattr(answer, "ask") else bool(answer)
    if pull:
        with console.status(f"Pulling {DEFAULT_EMBEDDING_MODEL}…"):
            ok = ollama_pull_embedding(DEFAULT_EMBEDDING_MODEL)
        if ok:
            console.print(f"[green]Pulled {DEFAULT_EMBEDDING_MODEL}.[/green]")
        else:
            console.print("[red]Pull failed. Notes will fall back to text search; run `ollama pull " + DEFAULT_EMBEDDING_MODEL + "` later.[/red]")
    else:
        console.print("[dim]Skipped. Notes will fall back to text search until an embedding model is pulled.[/dim]")


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
        think = config.get("ollama_think", None)
        if think is None:
            console.print("thinking: [bold]model default[/bold]")
        elif think:
            console.print("thinking: [bold]on[/bold]")
        else:
            console.print("thinking: [bold]off[/bold] (ollama_think=false)")
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


def main_with_args(argv):
    """Entry point accepting an argv list (testable); mirrors main()'s sys.exit behaviour."""
    sys.argv = list(argv)
    try:
        main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


NOTES_SUBCOMMAND_HELP = {
    "browse": "interactive browser: list, view, edit in $EDITOR, delete",
    "list": "list notes (optionally filtered by tag: ask notes list #ops)",
    "show": "print one note: ask notes show <title-or-slug>",
    "add": 'create a note: ask notes add "text" (no args opens $EDITOR); import files: ask notes add my-folder/*.md (.md/.txt)',
    "edit": "edit one note in $EDITOR: ask notes edit <title-or-slug>",
    "delete": "delete one note (asks confirmation): ask notes delete <title-or-slug>",
    "search": "search notes semantically (text fallback when no embedding provider)",
    "reindex": "force a full rebuild of the notes index",
}


def notes_command(argv):
    """Handle `ask notes <subcommand>`; argv is the words after 'notes'."""
    parser = argparse.ArgumentParser(
        prog="ask notes",
        description="Manage your personal notes (~/.ask-notes/*.md)",
        epilog=(
            "notes are plain markdown: title is the first line, inline #tags anywhere.\n"
            "the assistant consults them automatically when answering queries and\n"
            "cites them as [note: Title](file://path); it can save notes but never delete them."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("subcommand", nargs="?", default="browse",
                        choices=list(NOTES_SUBCOMMAND_HELP),
                        help="subcommand to run (default: browse)")
    parser.add_argument("args", nargs="*", help="subcommand arguments (title, slug, query, tag)")

    # Per-subcommand help: `ask notes add --help` etc. Checked before parsing
    # because argparse's own -h action would print-and-exit first.
    if "-h" in argv or "--help" in argv:
        ns_approx, _ = parser.parse_known_args([a for a in argv if a not in ("-h", "--help")])
        lines = [parser.format_help()]
        if ns_approx.subcommand in NOTES_SUBCOMMAND_HELP:
            lines.append(f"\n{ns_approx.subcommand}: {NOTES_SUBCOMMAND_HELP[ns_approx.subcommand]}")
        else:
            lines.append("\nsubcommands:")
            for name, desc in NOTES_SUBCOMMAND_HELP.items():
                lines.append(f"  {name:9s} {desc}")
        print("\n".join(lines).rstrip())
        return 0

    ns, remaining = parser.parse_known_args(argv)
    args_text = " ".join(ns.args + remaining)

    store = default_notes_store()
    from ask.notes_ui import (
        browse,
        cmd_add,
        cmd_delete,
        cmd_edit,
        render_note_list,
        _print_note,
    )
    from ask.notes_index import NotesIndex

    config = Config()
    provider = config.get("provider", "mock")

    def _search():
        if not args_text.strip():
            _err_console().print("[red]Usage: ask notes search <query>[/red]")
            return 1
        index = NotesIndex(notes_store=store)
        with console.status("Searching notes…"):
            results = index.search(args_text, provider=provider, config=config, top_k=5)
        if not results:
            console.print("[yellow]No matching notes.[/yellow]")
            return 0
        notice = next((r.notice for r in results if r.notice), "")
        if notice:
            console.print(f"[dim]{notice}[/dim]")
        for r in results:
            console.print(f"[bold]{r.title}[/bold] [dim]({r.path.name})[/dim] [cyan]{' '.join('#' + t for t in r.note.tags)}[/cyan] score={r.score:.3f}")
            console.print(f"  [dim]{r.snippet}[/dim]")
        return 0

    sub = ns.subcommand
    if sub == "browse":
        return browse(store)
    if sub == "list":
        notes = store.list_notes()
        if ns.args:
            tag = ns.args[0].lstrip("#")
            notes = [n for n in notes if tag in n.tags]
        if not notes:
            console.print("[yellow]No notes yet — run [bold]`ask notes add`[/yellow]")
            return 0
        render_note_list(notes)
        return 0
    if sub == "show":
        if not args_text.strip():
            _err_console().print("[red]Usage: ask notes show <title-or-slug>[/red]")
            return 1
        note = store.find(args_text.strip())
        if note is None:
            _err_console().print(f"[red]Note not found: {args_text.strip()}[/red]")
            return 1
        _print_note(note)
        return 0
    if sub == "add":
        return cmd_add(store, args_text, tokens=list(ns.args + remaining))
    if sub == "edit":
        if not args_text.strip():
            _err_console().print("[red]Usage: ask notes edit <title-or-slug>[/red]")
            return 1
        return cmd_edit(store, args_text.strip())
    if sub == "delete":
        if not args_text.strip():
            _err_console().print("[red]Usage: ask notes delete <title-or-slug>[/red]")
            return 1
        return cmd_delete(store, args_text.strip())
    if sub == "search":
        return _search()
    if sub == "reindex":
        index = NotesIndex(notes_store=store)
        result = index.reindex(provider=provider, config=config)
        n = result.get("total", 0)
        console.print(f"[green]Indexed {n} note{'s' if n != 1 else ''}.[/green]")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    main()
