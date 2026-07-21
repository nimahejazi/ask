import sys
from ask.config import Config
from ask.provider import MockProvider, Provider, OllamaProvider

def get_provider(name: str, config: Config) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        base_url = config.get("ollama_base_url", OllamaProvider.DEFAULT_BASE_URL)
        model = config.get("ollama_model", OllamaProvider.DEFAULT_MODEL)
        return OllamaProvider(base_url=base_url, model=model)
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
        provider = get_provider(provider_name, config)
    except NotImplementedError as e:
        print(e)
        sys.exit(1)

    response = provider.chat(query)
    print(response)

if __name__ == "__main__":
    main()
