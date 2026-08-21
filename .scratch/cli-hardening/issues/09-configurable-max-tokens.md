# 09 — Configurable max_tokens

**What to build:** Response length cap becomes configurable via the config file (`max_tokens`). It is applied to the Anthropic payload (where it is mandatory) and passed through to OpenAI-compatible providers when set; unset keeps today's defaults. `-S/--show-config` displays the current value.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Setting `max_tokens` in config changes the outgoing payload (test asserts payload contents)
- [x] Unset → current behaviour preserved (Anthropic default stays 1024)
- [x] Nonsense values rejected or clamped with a warning
- [x] `show-config` displays the effective value
