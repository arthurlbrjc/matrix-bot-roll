# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See [README.md](README.md) for what this project is, setup, and commands.

## Python standards

- Follow PEP 8 and PEP 257 (docstrings) unless existing code in this repo clearly does otherwise.
- Use type hints on function signatures.
- Prefer f-strings over `.format()` or `%`.
- Keep imports ordered: standard library, then third-party, then local — each group alphabetized.
- Order top-level vars/functions/methods newspaper-style: public before private (`_`-prefixed), and within each visibility group, callers before callees — if `a` calls `b`, `a` comes first — so the file reads top-to-bottom like a story.
- Code must be formatted with black, pass flake8, and pass mypy (`invoke check`) before being considered done.