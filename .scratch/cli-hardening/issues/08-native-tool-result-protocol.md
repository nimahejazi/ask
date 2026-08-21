# 08 — Native tool-result protocol, multi-round loop

**What to build:** Tool results are sent back to the provider using each API's native shape instead of being smuggled in as fake user messages: `role:"tool"` messages with the originating call id for OpenAI-compatible providers, `tool_result` content blocks for Anthropic. The assistant's tool-call turn is preserved verbatim in history. The model may chain further tool calls — the CLI keeps looping until the model answers without requesting tools, bounded by a safety cap.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] OpenAI-compatible path sends `role:"tool"` messages carrying tool call ids; Anthropic path sends `tool_result` blocks
- [x] Assistant turns containing tool calls are stored in history unmodified (not replaced by error strings or summaries)
- [x] Two-round scenario passes with a scripted mock provider: model requests a tool, gets a result, then requests a second tool before answering
- [x] Loop safety cap (e.g. 5 rounds) stops runaway chains with a clear message
- [x] Tool errors feed back to the model as failed tool results instead of aborting the conversation
