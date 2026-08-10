# 04 — Add integration tests for version flags

**What to build:** End-to-end tests that run the CLI subprocess with `-v` and `--version`.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Subprocess test: `python -m ask.cli -v` captures stdout == `"0.1.0\n"`
- [ ] Subprocess test: `--version` same output
- [ ] Test that version flag ignores other flags (e.g., `ask -v --help` → shows version, not help)
- [ ] Tests pass without requiring `.askrc` to exist
