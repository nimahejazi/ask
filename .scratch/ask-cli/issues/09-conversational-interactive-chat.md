Status: resolved

# 09 — Conversational Interactive Chat

**What to build:** Enhance the `--it` flag to support session memory, markdown rendering, and improved UX.

**Blocked by:** 04 — Stateless Interactive Chat

**Status:** resolved

- [x] Update `Provider` interface and implementations to support conversation history
- [x] Implement message tracking in the interactive loop in `ask/cli.py`
- [x] Support initial query processing when `--it` is passed with text
- [x] Remove welcome greeting from interactive mode
- [x] Integrate `rich` for markdown rendering of AI responses
- [x] Verify conversational memory via integration tests in `tests/test_cli.py`

## Comments
