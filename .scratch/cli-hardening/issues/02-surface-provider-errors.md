# 02 — Surface provider errors loudly

**What to build:** When a provider call fails — connection refused, invalid API key, HTTP error, mid-stream failure — the user sees a clear error message on stderr and the CLI exits with a non-zero status. Today every streaming method swallows all exceptions silently (and cloud providers `return` on 401), so a bad key produces blank output and exit code 0.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Invalid Anthropic key → visible auth error, in both streaming and non-streaming modes
- [x] Invalid OpenAI/ChatGPT key → same
- [x] Ollama/LM Studio unreachable → connection error naming the base URL
- [x] CLI exits non-zero whenever the turn ended in an error instead of a real answer
- [x] No bare swallow-and-continue exception handling remains on response paths; `-c` mode does not print error text as if it were a command
