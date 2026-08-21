# 12 — CI workflow running pytest

**What to build:** GitHub Actions runs the test suite on every push and PR, across the supported Python range established by ticket 05 (floor 3.9). No more landing on a green local run only.

**Blocked by:** 05 — Fix minimum-Python claim (bump floor to 3.9) (matrix versions depend on the supported floor).

**Status:** done

- [x] Workflow triggers on push and pull_request
- [x] Installs package + dev requirements, then runs pytest
- [x] Matrix covers 3.9–3.12
- [x] Workflow passes on a clean checkout
