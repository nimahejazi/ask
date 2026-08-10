try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w
from pathlib import Path
from typing import Any

SYSTEM_PROMPT_PATH = Path.home() / ".ask-sys-prompt"
DEFAULT_SYSTEM_PROMPT = """# System Prompt for ask CLI

You are a command-line focused AI assistant. Your role is to help users complete tasks efficiently using terminal commands, shell workflows, and direct execution.

## Key Principles

- **CLI-first**: Emphasize command-line tools and terminal-based solutions
- **Concise responses**: Provide direct answers with minimal preamble
- **Action-oriented**: Focus on runnable commands andexecutable steps
- **No fluff**: Skip introductions, conclusions, and explanations unless asked

## When responding

1. Read existing files before making changes
2. Prefer incremental edits over rewrites
3. Use proper command-line flags and options
4. Handle errors gracefully with actionable feedback

## Safety

- Don't run destructive commands without confirmation
- Never expose API keys or credentials
- Verify file paths before operations
"""

CONFIG_PATH = Path.home() / ".askrc"

class Config:
    def __init__(self):
        self.data: dict[str, Any] = {}
        self.load()

    def load(self):
        self._load_system_prompt_from_file()
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "rb") as f:
                self.data = tomllib.load(f)

    def _ensure_prompt_file_exists(self):
        if not SYSTEM_PROMPT_PATH.exists():
            with open(SYSTEM_PROMPT_PATH, "w") as f:
                f.write(DEFAULT_SYSTEM_PROMPT)

    def _load_system_prompt_from_file(self):
        self._ensure_prompt_file_exists()
        with open(SYSTEM_PROMPT_PATH, "r") as f:
            prompt_content = f.read()
            if prompt_content.strip():
                self.data["system_prompt"] = prompt_content
            elif not CONFIG_PATH.exists():
                self.data["system_prompt"] = prompt_content

    def save(self):
        with open(CONFIG_PATH, "wb") as f:
            tomli_w.dump(self.data, f)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

    def exists(self) -> bool:
        return CONFIG_PATH.exists()

    def _set_path(self, path: Path):
        global CONFIG_PATH
        CONFIG_PATH = path
