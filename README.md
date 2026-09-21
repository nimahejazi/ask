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

# Notes-only mode (answer strictly from your personal notes)
ask -n "what's six sigma DMIAC?"

# Skip notes for this query
ask -N "What is the capital of France?"

# Notes
ask notes                       # interactive browser (list, view, edit, delete)
ask notes add "Deploy Checklist\nrun kubectl first #ops"
ask notes add my-folder/*.md    # import .md/.txt files (globs, dirs, paths) as notes
ask notes list [--tag ops]
ask notes show deploy-checklist
ask notes edit deploy-checklist      # opens $EDITOR
ask notes delete deploy-checklist
ask notes search "kubectl rollout"
ask notes reindex
```

## Notes

`ask` keeps personal notes (`~/.ask-notes/*.md`, plain markdown — title is the first
line, inline `#tags` allowed anywhere) and consults them when answering questions:

- **Default on**: every query gets `search_notes` / `read_note` / `save_note` tools,
  so the assistant can look up a relevant note, cite it as
  `[note: Title](file://path)`, and save new notes when you ask it to.
  Use `-N/--no-notes` to skip notes for a query, or `-n/--notes-only` to answer
  strictly from notes (no general knowledge). AI cannot delete notes — use
  `ask notes delete`. Read-only note tools run without confirmation; `save_note`
  still asks.
- **Semantic search**: notes are embedded with your provider's embedding endpoint
  (ollama: `nomic-embed-text` — offered at setup; ChatGPT: `text-embedding-3-small`;
  LM Studio: its loaded embedding model). Providers without embeddings (Anthropic,
  Mock) fall back to keyword search automatically.
- **Files are the source of truth**: edit `~/.ask-notes/*.md` by hand anytime;
  the index rebuilds lazily (or force one with `ask notes reindex`).

## Configuration

Run `ask` once to configure your preferred LLM provider (Mock, Ollama, LM Studio, Anthropic, or ChatGPT).

### API Keys and Environment Variables

For Anthropic and ChatGPT providers, you can set your API key either in the config file (via `ask` interactive setup) or via environment variables. Environment variables are read without writing to the config file:

- `ANTHROPIC_API_KEY` — for Anthropic
- `OPENAI_API_KEY` — for ChatGPT (OpenAI-compatible)

Precedence: a key stored in `~/.askrc` takes precedence over the environment variable. If no key is stored in config, the environment variable is used. `ask --show-config` indicates whether a key is set without ever printing its value, and key entry is masked (no echo) in the terminal.
