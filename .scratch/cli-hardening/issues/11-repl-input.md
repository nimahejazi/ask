# 11 — Proper REPL input for interactive mode

**What to build:** `ask --it` reads input through a real line-editing prompt instead of bare stdin: arrow-key history within the session, Ctrl-C cancels the current line and returns to a fresh prompt (instead of killing the session), Ctrl-D exits cleanly, and typing `exit` still works. Streaming and history behaviour are untouched.

**Blocked by:** 01 — Remember streamed replies in session history (both rewrite the same interactive loop; sequencing avoids conflicts).

**Status:** done

- [x] Up-arrow recalls earlier queries in the session; down-arrow returns
- [x] Ctrl-C mid-input clears the line without exiting; Ctrl-C at output does not crash
- [x] Ctrl-D exits cleanly with no traceback
- [x] `exit` command still ends the session
- [x] New dependency added to package metadata; install-from-source still works
