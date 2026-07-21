# 04 — Stateless Interactive Chat

**What to build:** The `--it` flag allowing a conversational loop with the AI that remains stateless (context is cleared upon exit).

**Blocked by:** 01 — Configuration & Mock Core

**Status:** ready-for-agent

- [x] Implement input loop when `--it` is passed
- [x] Support "exit" keyword to terminate session
- [x] Verify context is not persisted across different tool invocations
