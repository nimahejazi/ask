# 06 — Tool Execution Loop

**What to build:** The internal logic to execute a tool requested by the LLM (running the local script) and feeding the output back to the model to complete the task.

**Blocked by:** 05 — Tool Definition Extraction

**Status:** ready-for-agent

- [x] Detect "tool_call" in LLM response
- [x] Execute the corresponding local script with provided arguments
- [x] Return script output to the LLM and display final synthesized answer to user
