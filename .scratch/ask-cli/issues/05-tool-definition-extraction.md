# 05 — Tool Definition Extraction

**What to build:** Ability to use the `-t <path>` flag to parse `# @tool:` comments from Python/TS scripts and pass those definitions to the LLM as available tools.

**Blocked by:** 01 — Configuration & Mock Core, 02 — Real LLM Integration

**Status:** ready-for-agent

- [x] Regex parser extracts tool name, description, and args from `# @tool: ...` comments
- [x] Parsed definitions are converted to the provider's specific tool schema
- [x] Passing `-t <path>` successfully includes these tools in the LLM request
