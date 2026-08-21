# 13 — Repo hygiene

**What to build:** Root-level junk removed so the repo reads clean: the placeholder `package.json` stub goes away, the developer diagnostic script moves out of the repo root into a scripts area (or gets deleted if obsolete), and build artifacts are properly ignored by git.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Placeholder `package.json` removed or justified in README
- [x] Diagnostic script relocated out of repo root (and still runnable) or deleted
- [x] Build/dist artifacts ignored by git; nothing stale tracked
- [x] No references to moved/deleted files remain anywhere in docs, workflows, or tests
