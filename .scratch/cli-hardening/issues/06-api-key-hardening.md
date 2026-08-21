# 06 — Hide API-key entry, honor env vars

**What to build:** Configuring Anthropic or ChatGPT no longer echoes the key to the terminal while typing, and well-known environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are honored when no key is stored in config. Precedence: explicit value stored in config wins; env var used only when config has none; documented in README.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Interactive key entry is masked (no terminal echo)
- [x] Fresh setup picks up keys from env vars without writing them to the config file
- [x] Stored config value takes precedence over env var (test covers both directions)
- [x] `show-config` never prints key values, only whether one is set
- [x] README documents supported variable names and precedence
