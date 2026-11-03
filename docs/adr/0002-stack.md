# ADR-0002: Application stack

Status: **Proposed**. CLAUDE.md s12 says to confirm before locking in.

## Decision (proposed)
| Concern | Choice |
|---|---|
| Language, packaging | Python 3.12, `uv` with a committed lockfile |
| Config and domain validation | pydantic v2; pandera for data tables (Phase 2) |
| Demand model | CatBoost (quantile outputs); LightGBM challenger |
| Optimisation | OR-Tools or PuLP for transfers and surplus matching |
| API | FastAPI |
| Database | Postgres (Cloud SQL), SQLite for local tests; Alembic migrations |
| Frontend | React + Vite progressive web app |
| Quality | ruff, mypy (strict), pytest, Hypothesis, Playwright (Phase 8) |
| CI | GitHub Actions |

## Why Python 3.12
Local machine has 3.14, but CatBoost and OR-Tools wheels for newest Python releases lag.
`.python-version` pins 3.12; `uv` fetches it.

## Open
Optimiser library, and whether to add MLflow later, are decided when Phase 5 and 6 start.
