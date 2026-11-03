# ADR-0003: One Python package, and validated config

Status: **Accepted** (2026-11-03). Deviates from CLAUDE.md s14; see below.

## Context
CLAUDE.md s14 lists `data/`, `features/`, `models/`, `state/` and so on as top-level folders.
Top-level modules with those names collide with common library names and make imports
ambiguous (`import models`, `import data`).

## Decision
1. All code lives in one installable package `harabhara/`, with the same subpackage names as
   CLAUDE.md s14. `config/`, `tests/`, `docs/`, `frontend/` stay at the top level.
2. The loader lives in `harabhara/settings/` (not `harabhara/config/`) so it can't be confused
   with the top-level `config/` data folder.
3. Every file in `config/` is validated by pydantic with unknown keys rejected. A value the
   playbook doesn't give is `null`; `require()` raises `PlaceholderError` if code needs it.
4. Each run pins `AppConfig.digest`, a SHA-256 over the four files.

## Consequences
- CLAUDE.md s14 should be updated to match; that file is the owner's, so it's left unchanged
  until approved.
- A typo in a rule name fails at load time instead of silently disabling a rule.
