# 06 — Tool Execution Loop ✅ COMPLETE

**What to build:** The internal logic to execute a tool requested by the LLM (running the local script) and feeding the output back to the model to complete the task.

**Blocked by:** 05 — Tool Definition Extraction

**Status:** complete

## Implementation Summary:

- [x] Detect "tool_call" in LLM response
- [x] Execute the corresponding local script with provided arguments  
- [x] Return script output to the LLM and display final synthesized answer to user

## Key Changes:

1. **Provider Layer** (`ask/provider.py`):
   - Changed return type from `str` to `dict` (content + tool_calls)
   - Added `supports_tools()` classmethod to check model capability
   - Updated Ollama/LMStudio providers with proper error handling

2. **Tool Execution Loop** (`ask/cli.py`):
   - Detects when LLM returns `tool_calls`
   - Executes matching local scripts with JSON arguments
   - Feeds tool output back to LLM for final answer synthesis

3. **Tool Definitions**:
   - Parse `# @tool: name | description | params` format
   - Convert to OpenAI/Ollama schema
   - Only send tools if model supports them (otherwise warn user)

## Testing:

Created `/Users/nima/Codes/ask/test_sample_tool.py` for testing.

Run tests: `python3 -m pytest tests/`

All 16 tests passing ✓

(End of file - total 45 lines)