# 03 — Command Mode & System Prompts

**What to build:** The `-c` flag to extract only executable command blocks from the response, and support for custom system prompts defined in `~/.askrc`.

**Blocked by:** 01 — Configuration & Mock Core

**Status:** ready-for-agent

- [ ] Support for a custom system prompt in `.askrc` is integrated into the request
- [ ] `-c` flag correctly parses and displays only the code block from the AI response
- [ ] CLI behaves normally (conversational) when `-c` is omitted
