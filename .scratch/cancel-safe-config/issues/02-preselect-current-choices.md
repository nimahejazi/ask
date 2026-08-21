# 02 — Pre-select current choices in `-M` prompts

**What to build:** Reopening `ask -M` starts with your current provider already highlighted, and the model prompt starts with your current model highlighted when it appears in the fetched list. Pressing Enter keeps the current choice, making "just look and bail out" a no-op rather than an accidental change.

**Blocked by:** 01 — Cancelling `-M` never corrupts config (both touch the same prompt sites; land the safety guard first).

**Status:** done

- [x] Provider select defaults to the currently configured provider
- [x] Model select defaults to the currently configured model when present in the fetched list; falls back gracefully when it isn't
- [x] Test asserts the current provider/model is passed as the default choice
