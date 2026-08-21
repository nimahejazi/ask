# 07 — Confirm before executing model-requested tools

**What to build:** Before any tool script is executed on the model's request, the CLI shows the tool name and its arguments and asks for y/N confirmation. A `-y/--yes` flag skips prompting for scripting use. This enforces what the default system prompt already promises ("don't run destructive commands without confirmation").

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Default behaviour: prompt showing tool name + arguments before each execution; declining skips that tool
- [x] Declined tool produces a graceful message to the model rather than a crash
- [x] `-y` bypasses all prompts (covered by test)
- [x] Non-interactive stdin behaves safely: no prompt hang — treated as decline unless `-y`
- [x] Existing tool execution tests updated/extended for the gate
