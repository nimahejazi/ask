Status: ready-for-agent
# Spec: ask CLI Tool

## Problem Statement

Users need a fast, low-friction way to get actionable AI assistance (like shell commands or quick answers) directly from their terminal without leaving the command line or navigating complex web interfaces.

## Solution

A Python-based CLI tool named `ask` that provides a streamlined interface for interacting with various LLM providers. It allows users to quickly fetch executable commands, engage in stateless interactive chats, and extend AI capabilities by providing local scripts as tools.

## User Stories

1. As a user, I want to run `ask "how to list files by size"` so that I get a quick answer.
2. As a user, I want to use the `-c` flag so that only the executable command is returned without conversational filler.
3. As a user, I want to start the tool for the first time and be prompted to configure my provider (Ollama, ML Studio, ChatGPT, Anthropic, or OpenAI Compatible) so that I don't have to manually edit config files.
4. As a user, I want my configuration stored in `~/.askrc` as TOML so that it is easy to manage and supports multi-line strings.
5. As a user, I want to set a custom agent prompt in the config so that the AI behaves according to my specific preferences.
6. As a user, I want to use the `--it` flag to enter an interactive chat mode for follow-up questions.
7. As a user, I want my interactive session to maintain context during the conversation so that I can ask follow-up questions based on previous turns, but remain stateless across different tool invocations.
8. As a user, I want AI responses in the terminal to be rendered with markdown formatting (bold, lists, code blocks), so they are easier to read.
9. As a user, I want to pass an initial query when starting interactive mode (e.g., `ask "hi" --it`), so that the conversation starts with my first request immediately.
10. As a user, I want the CLI to be quiet and avoid unnecessary welcome messages when entering interactive mode.
11. As a user, I want to pass a specific local script using the `-t` flag so that the AI can use that script as a tool to perform a task.
12. As a developer, I want to define tools in Python or TS scripts using a `# @tool: name | description | args` format so that `ask` can automatically extract and present them to the LLM.
13. As a user, I want to install the tool via Homebrew for easy installation and updates on macOS.

## Implementation Decisions

- **Language**: Python (for rapid development and strong library support for CLI/AI).
- **Configuration**: 
    - File: `~/.askrc`
    - Format: TOML (using `tomllib` for parsing in Python 3.11+).
    - Handles multi-line strings for system prompts via TOML's triple-quote syntax.
- **Provider Architecture**:
    - Use a `Provider` interface/abstract base class with a consistent `Chat` method.
    - Specific implementation classes for Ollama, ML Studio, ChatGPT, Anthropic, and OpenAI Compatible providers.
- **Tool Extraction**:
    - Use regex to parse structured comments (`# @tool: ...`) from provided files in Python or TS scripts to generate LLM tool definitions.
- **CLI Interface**:
    - Flag `-c`: Post-processes the AI response to extract only the command block.
    - Flag `--it`: Loops user input and model output until a termination keyword (e.g., "exit") is encountered.
    - Flag `-t <path>`: Loads tool definitions from the specified file path.

## Testing Decisions

- **External Behavior**: Tests will focus on CLI input/output and config file state rather than internal function calls.
- **CLI Integration Tests**: Use a test runner to execute `ask` with various arguments and assert against the expected output string or exit code.
- **Provider Mocking**: Implement a `MockProvider` that returns deterministic responses to verify prompt assembly, tool parsing, and `-c` extraction logic without needing actual API keys.

## Out of Scope

- Running commands automatically (the requested `-r` functionality is skipped for this version).
- Persistent chat history across different sessions.
- Complex tool orchestration or recursive tool calling.
- GUI components.

## Further Notes

The simplicity of the regex-based tool extraction is a priority over formal AST parsing to keep the codebase maintainable and lightweight.
