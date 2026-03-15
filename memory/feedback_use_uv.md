---
name: Use uv for Python tooling
description: Project uses uv as the Python package manager and task runner, not pip directly
type: feedback
---

Use `uv` for all Python package management and running commands (e.g., `uv run --directory demo mkdocs build`). Do not use `pip install` directly.

**Why:** User preference — this is their standard tooling.
**How to apply:** Always use `uv run` to execute project commands and `uv` for dependency management.
