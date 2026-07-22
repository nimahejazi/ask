# Sample Tool Testing

To test the tool execution loop with Ollama:

1. Ensure Ollama is running: `ollama serve`
2. Use a model that supports tools (like Qwen2.5-Coder):
   ```bash
   python3 -m ask.cli -t test_sample_tool.py "What's the weather in Paris?"
   ```

If the model doesn't support native tool calling, you'll see:
```
Warning: Model 'xxx' does not support native tool calling. Tools will be ignored.
Mock response to: What's the weather in Paris? (Tools provided: ['get_weather'])
```

The actual workflow is:
1. CLI parses `# @tool:` comments from the script
2. Sends tool definitions to LLM with user query
3. If model returns `tool_calls`, executes matching local scripts
4. Feeds output back to LLM for final synthesized answer
