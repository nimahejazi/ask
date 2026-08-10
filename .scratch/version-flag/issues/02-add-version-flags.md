# 02 — Add `-v`/`--version` flags to CLI argument parser

**What to build:** Register the version flags with argparse so `ask -v` and `ask --version` parse without errors.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `argparse.ArgumentParser` accepts `-v` and `--version` flags
- [ ] Both flags trigger the same behaviour (print version to stdout)
- [ ] Version flag works even when `.askrc` doesn't exist yet
- [ ] Unit test: `test_version_flag_output()` mocks `sys.argv` and `sys.stdout`
