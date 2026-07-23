# ask

AI CLI tool for natural language interaction with LLMs.

## Installation

### Using Homebrew (macOS)

```bash
brew install nimahejazi/tap/ask
brew update
brew upgrade ask
```

### From Source

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
