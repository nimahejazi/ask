# 03 — Probe tool support once, with real credentials

**What to build:** Tool-capability detection happens at most once per session instead of firing a live "test" LLM request before every single chat call, and the ChatGPT/OpenAI-compatible probe authenticates with the user's real API key so tools are not permanently disabled there (today it probes with a hardcoded bogus token, fails, and silently drops tools).

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Capability probe fires once per session/provider instance; subsequent chat calls reuse the cached result (test asserts request count)
- [x] OpenAI tools are offered to the model when a valid API key is configured
- [x] Models without tool support still degrade gracefully with the existing warning
- [x] Probe failure does not crash the turn — falls back to "tools unsupported" behaviour
