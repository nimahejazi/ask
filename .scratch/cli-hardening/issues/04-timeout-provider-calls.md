# 04 — Timeout every provider HTTP call

**What to build:** All provider HTTP requests carry an explicit timeout so a hung endpoint can never freeze the CLI indefinitely. Metadata calls already time out; the main chat/stream calls currently do not.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Every chat / stream request passes an explicit timeout (generous default, e.g. 120s)
- [x] Timeout expiry surfaces as a normal provider error per ticket 02 behaviour ("endpoint did not respond in Ns")
- [x] Test asserts the timeout is passed on chat, stream, and model-list requests
