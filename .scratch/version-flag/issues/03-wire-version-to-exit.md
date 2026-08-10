# 03 — Wire version flag to print version and exit

**What to build:** When `-v` or `--version` is detected, print the version string (from ticket 01) to stdout and exit with code 0.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] `ask -v` prints `0.1.0\n` to stdout
- [ ] `ask --version` prints same output as `-v`
- [ ] Process exits immediately (no config loading, no provider init)
- [ ] Unit test: `test_version_flag_exits_early()` verifies exit code 0
