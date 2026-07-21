# 02 — Real LLM Integration

**What to build:** End-to-end connectivity with a real provider (e.g., Ollama or OpenAI Compatible). The user can get actual AI responses based on their configured API keys/endpoints.

**Blocked by:** 01 — Configuration & Mock Core

**Status:** ready-for-agent

- [ ] Implement `Provider` concrete classes for at least one real service (e.g., Ollama)
- [ ] API requests are correctly formed using config values from `~/.askrc`
- [ ] Response body is extracted and returned to the CLI output
