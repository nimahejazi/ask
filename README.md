# ask

AI CLI tool for natural language interaction with LLMs.

## Installation

### Using Homebrew (macOS)

First, add and trust the tap:

```bash
brew tap nimahejazi/tap
brew install nh-ask-cli
brew upgrade nh-ask-cli
```

Note: You may need to run `brew trust nimahejazi/tap` if Homebrew requires verification.

### From Source

Requires Python 3.9 or later.

```bash
git clone https://github.com/nimahejazi/ask.git
cd ask
pip install -e .
```

## Usage

```bash
# Interactive chat mode
ask --it

# Quick query
ask "What is the capital of France?"

# Command mode (extract only executable commands)
ask -c "List files in current directory"

# With tools
ask -t ./tools.sh "Do something with tools"
```

## Configuration

Run `ask` once to configure your preferred LLM provider (Mock, Ollama, LM Studio, Anthropic, or ChatGPT).

### API Keys and Environment Variables

For Anthropic and ChatGPT providers, you can set your API key either in the config file (via `ask` interactive setup) or via environment variables. Environment variables are read without writing to the config file:

- `ANTHROPIC_API_KEY` — for Anthropic
- `OPENAI_API_KEY` — for ChatGPT (OpenAI-compatible)

Precedence: a key stored in `~/.askrc` takes precedence over the environment variable. If no key is stored in config, the environment variable is used. `ask --show-config` indicates whether a key is set without ever printing its value, and key entry is masked (no echo) in the terminal.
