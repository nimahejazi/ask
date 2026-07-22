import sys
import argparse
import re
import questionary
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

def handle_response(response: str, extract_command_only: bool):
    if extract_command_only:
        print(extract_command(response))
    else:
        console.print(Markdown(response))

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
                
                # Use a copy of messages to avoid mutating the history passed to provider if it's modified elsewhere
                response = provider.chat(user_input, system_prompt=system_prompt, history=list(messages), tools=tools)
                handle_response(response, args.command)
                
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": response})
                
                initial_query = None
            except (EOFError, KeyboardInterrupt):
                break
        return

    response = provider.chat(query, system_prompt=system_prompt, tools=tools)
    handle_response(response, args.command)

if __name__ == "__main__":
    main()
