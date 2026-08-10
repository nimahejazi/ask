# 01 — Extract version string from package metadata

**What to build:** A single function that returns the current app version by reading `ask/__init__.py`'s `__version__` variable.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The `get_version()` function reads `ask.__init__.__version__`
- [ ] Unit test: `test_get_version_returns_string_like("0.1.0")`
- [ ] No imports from `rich`, `questionary`, or other heavy deps (keep it pure)
