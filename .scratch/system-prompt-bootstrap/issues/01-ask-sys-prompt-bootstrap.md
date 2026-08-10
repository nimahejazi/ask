# 01 — `~/.ask-sys-prompt` bootstrap

**What to build:** On first run, ask checks for `~/.ask-sys-prompt`; if absent, creates it with a concise, CLI-focused system prompt in markdown format. The prompt should omit preamble and deliver direct, actionable responses.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Checks for existence of `~/.ask-sys-prompt`
- [ ] If missing, writes default CLI-focused system prompt in markdown
- [ ] Prompt emphasizes terminal commands, shell workflows, and direct execution
- [ ] No modification if file already exists with content
- [ ] Hook into ask's startup sequence to run before user input
