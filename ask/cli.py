import sys
from ask.config import Config
from ask.provider import MockProvider, Provider

def get_provider(name: str) -> Provider:
    if name == "mock":
        return MockProvider()
    # Other providers will be added in ticket 02 and 07
    raise NotImplementedError(f"Provider {name} not implemented")

def main():
    config = Config()
    
    if not config.exists():
        print("First run detected. Configuring ask...")
        provider_choice = input("Choose a provider (mock, ollama, openai): ").strip() or "mock"
        config.set("provider", provider_choice)
        # In real providers we would prompt for API keys here
        print(f"Configured to use {provider_choice} provider.\n")

    query = " ".join(sys.argv[1:])
    if not query:
        print('Usage: ask "your query"')
        sys.exit(1)

    provider_name = config.get("provider", "mock")
    try:
        provider = get_provider(provider_name)
    except NotImplementedError as e:
        print(e)
        sys.exit(1)

    response = provider.chat(query)
    print(response)

if __name__ == "__main__":
    main()
