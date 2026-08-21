# 05 — Fix minimum-Python claim (bump floor to 3.9)

**What to build:** The package honestly declares and works with its supported Python range. Decision recorded here: **bump the floor to Python 3.9** (3.8 is EOL). The code already uses builtin generic annotations (`list[dict]`) that raise on import under 3.8, contradicting the declared `>=3.8` support.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Package metadata requires Python >=3.9 and classifiers drop 3.8
- [x] README installation section states the 3.9 floor
- [x] Full test suite passes on the oldest supported interpreter available locally
- [x] No annotation syntax newer than 3.9 remains unguarded
