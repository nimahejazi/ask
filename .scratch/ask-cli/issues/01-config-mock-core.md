# 01 — Configuration & Mock Core

**What to build:** The ability to run `ask "query"` and receive a deterministic response from a `MockProvider`, with configuration stored in `~/.askrc` (TOML). This establishes the config schema, the Provider interface, and the basic CLI entry point.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] Config file `~/.askrc` is created/read using TOML format
- [x] User is prompted for provider configuration on first run
- [x] Basic CLI entry point accepts a query string
- [x] A `MockProvider` returns deterministic responses for integration testing
