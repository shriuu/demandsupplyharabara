# Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-02 | Project at `~/harabhara-fresh`. Original pack copied to `source_readonly/` and made write-protected; analysis works on `work/` copies. | CLAUDE.md §2: data folder is read-only. The two pack folders in Downloads are byte-identical; one was used. |
| 2026-11-02 | Python venv at `.venv` (pandas, openpyxl, pyyaml). CatBoost, LightGBM and FastAPI not installed yet. | The stack in CLAUDE.md §12 is "proposed, confirm before locking in". |
| 2026-11-02 | Config drafted (`config/*.yaml`, v0.1.0-draft). Every value cites the playbook or brief; unknowns are `null` with an owner-question link. | CLAUDE.md §2: no hard-coded numbers. |
| 2026-11-02 | S07 outage rows: rebuild sales from stock arithmetic for lag features; exclude from training targets and metrics. | They are the only rows where arithmetic doesn't balance, so the rebuild is exact. Keeping them out of targets is the conservative choice. |
| 2026-11-02 | Festival uplift must be pooled across major festivals by intensity × product. | Varamahalakshmi and Ganesha Chaturthi (T3) occur only in the holdout. |
| 2026-11-02 | T5 (tomato price doubles in a week) will be tested with an injected scenario. | The data's maximum 7-day rise is 1.4×. |
