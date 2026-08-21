# 10 — One shared provider-setup flow

**What to build:** First-run configuration and `-M/--config-model` share a single implementation. Today the two flows are near-identical 40-line duplicates that have already drifted (only `-M` warns when model discovery fails). Behaviour stays the same from the user's perspective; the drift is resolved deliberately.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Provider selection + per-provider follow-up lives in exactly one place, used by both entry points
- [x] Both paths warn when local model discovery fails (drift resolved in favour of the warning)
- [x] Manual check: fresh-machine bootstrap and reconfigure behave identically
- [x] Existing config tests pass unchanged
