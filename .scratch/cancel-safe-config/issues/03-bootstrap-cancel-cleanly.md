# 03 — First-run setup cancels cleanly

**What to build:** Cancelling during first-run setup aborts without writing any configuration file. Today a cancel there crashes after creating a bogus empty `~/.askrc`, which permanently disables bootstrap (the CLI thinks it's configured) and silently runs on `mock` forever. After this ticket, a cancel during bootstrap exits cleanly with a "Setup cancelled." message and creates nothing.

**Blocked by:** 01 — Cancelling `-M` never corrupts config (bootstrap shares the guarded flow once the dedupe lands).

**Status:** done

- [x] Cancelling at the bootstrap provider prompt exits without creating or modifying `~/.askrc`
- [x] A later run still enters first-run setup normally
- [x] Test covers the bootstrap-cancel path with the prompt stubbed to return `None`
