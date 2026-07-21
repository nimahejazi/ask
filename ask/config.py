try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".askrc"

class Config:
    def __init__(self):
        self.data: dict[str, Any] = {}
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "rb") as f:
                self.data = tomllib.load(f)

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
