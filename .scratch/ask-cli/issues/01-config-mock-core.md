# 01 — Configuration & Mock Core

**What to build:** The ability to run `ask "query"` and receive a deterministic response from a `MockProvider`, with configuration stored in `~/.askrc` (TOML). This establishes the config schema, the Provider interface, and the basic CLI entry point.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Config file `~/.askrc` is created/read using TOML format
- [ ] User is prompted for provider configuration on first run
- [ ] Basic CLI entry point accepts a query string
- [ ] A `MockProvider` returns deterministic responses for integration testing
