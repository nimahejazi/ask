# 01 — Cancelling `-M` never corrupts config

**What to build:** Exiting `ask -M` before making a selection leaves the existing configuration completely untouched. Today, cancelling (Ctrl+C) at either the provider prompt or the Ollama/LM Studio model prompt writes a `None` value that truncates `~/.askrc` mid-write, leaving an empty config that silently falls back to the `mock` provider on the next run. After this ticket, a cancel at any prompt in the reconfigure flow prints "Configuration unchanged." instead of claiming success, and no config key is written.

**Blocked by:** [cli-hardening #10 — One shared provider-setup flow](../../cli-hardening/issues/10-dedupe-provider-setup-flow.md) — guards must land once in the shared flow, not twice in the duplicated copies it replaces.

**Status:** done

- [x] Cancelling at the provider prompt performs zero `config.set` calls; `~/.askrc` is byte-identical afterwards
- [x] Choosing ollama/lmstudio then cancelling the model prompt keeps the previously configured model (provider update still applies)
- [x] CLI reports the session as unchanged on cancel, never prints "Configuration updated!" unless something was saved
- [x] Tests cover both cancel paths by stubbing the prompts to return `None`
- [x] Manual smoke: configure a real provider, run reconfigure + Ctrl+C, diff the config file
