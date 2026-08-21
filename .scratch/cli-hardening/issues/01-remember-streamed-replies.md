# 01 — Remember streamed replies in session history

**What to build:** In an interactive `ask --it` session running on the streaming path, the assistant's streamed answer is kept in session history. From turn 2 onward the model can see (and refer back to) what it said on earlier turns, so follow-ups like "modify that last example" work. Today the streaming path stores an empty assistant entry for every turn.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Streaming path returns the accumulated full response text to the caller instead of discarding it
- [x] Interactive sessions append the accumulated text as the assistant history entry
- [x] Scripted test: two-turn mock-streamed session where the second answer depends on the first reply passes
- [x] Non-streaming path (`mock`, `-c`, tools) behaviour unchanged
