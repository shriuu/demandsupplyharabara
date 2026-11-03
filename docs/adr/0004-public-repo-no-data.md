# ADR-0004: The repository is public and holds no data pack

Status: **Accepted** (2026-11-03)

## Context
The GitHub repository (`shriuu/demandsupplyharabara`) is public. The data pack and brief belong
to the problem owner; whether they may be republished is unknown.

## Decision
- `source_readonly/`, `work/`, `outputs/` and data file types (`.xlsx`, `.csv`, `.parquet`,
  `.pkl`) are in `.gitignore`.
- The data pack is stored in a private Cloud Storage bucket (Phase 1) and fetched by script.
- No secrets, keys or GCP project IDs are committed; `detect-private-key` runs in pre-commit.
- Docs may state the brief's headline figures, which are needed to check the metric code.

## Consequences
- CI tests that need data use small synthetic fixtures generated in the tests.
- If the owner prefers a private repo, flip the setting; nothing else changes.
