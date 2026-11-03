# HaraBhara Fresh: demand and supply decision support (PS-10)

Forecasts demand by store and product, suggests evening orders and morning markdown, transfer
and surplus actions, and leaves every decision to a person. Read [CLAUDE.md](CLAUDE.md) first:
it is the project's memory and sets the guardrails.

All data is synthetic. The problem owner's data pack is **not** in this repository.

## Develop

```bash
uv sync                  # install, pinned by uv.lock
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy              # strict types
```

`uv sync --group explore` adds pandas and openpyxl for the scripts in `scripts/`.

## Layout

| Path | Purpose |
|---|---|
| `config/` | Playbook limits as validated YAML. Code reads these; nothing is hard-coded |
| `harabhara/` | The Python package: `settings`, `data`, `features`, `models`, `state`, `decisions`, `rules`, `reasons`, `workflow`, `api`, `sim` |
| `tests/` | Unit, property, scenario (T01 to T10), backend and frontend tests |
| `docs/` | `adr/` decision records, `traceability.yaml`, owner questions, data findings |
| `frontend/pwa/` | The role-based web app (Phase 8) |

## Build rules

- Every playbook rule, guardrail and acceptance scenario has an ID in
  [docs/traceability.yaml](docs/traceability.yaml). A row can leave `planned` only when its code
  and test exist.
- A value the playbook doesn't give is `null` in `config/` and raises `PlaceholderError` if code
  needs it. It never gets a guess.
- Work happens on a branch per phase and merges through a pull request with green CI.
