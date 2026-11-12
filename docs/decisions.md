# Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-02 | Project at `~/harabhara-fresh`. Original pack copied to `source_readonly/` and made write-protected; analysis works on `work/` copies. | CLAUDE.md §2: data folder is read-only. The two pack folders in Downloads are byte-identical; one was used. |
| 2026-11-02 | Python venv at `.venv` (pandas, openpyxl, pyyaml). CatBoost, LightGBM and FastAPI not installed yet. | The stack in CLAUDE.md §12 is "proposed, confirm before locking in". |
| 2026-11-02 | Config drafted (`config/*.yaml`, v0.1.0-draft). Every value cites the playbook or brief; unknowns are `null` with an owner-question link. | CLAUDE.md §2: no hard-coded numbers. |
| 2026-11-02 | S07 outage rows: rebuild sales from stock arithmetic for lag features; exclude from training targets and metrics. | They are the only rows where arithmetic doesn't balance, so the rebuild is exact. Keeping them out of targets is the conservative choice. |
| 2026-11-02 | Festival uplift must be pooled across major festivals by intensity × product. | Varamahalakshmi and Ganesha Chaturthi (T3) occur only in the holdout. |
| 2026-11-02 | T5 (tomato price doubles in a week) will be tested with an injected scenario. | The data's maximum 7-day rise is 1.4×. |
| 2026-11-03 | GCP setup: reuse an existing, unused project owned by the credit-holding account; region `asia-south1`; monthly budget INR 8,000 with alerts at 50%, 90%, 100% on that project. Phase 1 APIs enabled (Cloud Run, Artifact Registry, Cloud Build, Secret Manager, Firestore, IAM, STS, Budgets). Project ID and account are kept out of this public repo. | Trial credit INR 28,797 ends 2027-01-28 and sits on the owner's billing account; the next owner must attach their own billing before then or the site stops. |
| 2026-11-03 | Go-live target 2026-11-12, then handover. Scope: store-manager, area-manager, DC-lead and farmer-coordinator screens, markdown timing optimiser, chat assistant (OpenAI behind a provider-neutral interface), live mandi prices. Voice, translations, offline mode, usability study and multi-environment split deferred. | Owner decision; nine days. |
| 2026-11-03 | Farmer commitments: confirmed farmer-group volume is never reduced; what the system changes is where that harvest goes (between stores, to surplus buyers). Mandi spot buying stays a suggestion-only lever for the DC lead. Proposed wording change to CLAUDE.md guardrail 3, pending owner approval. | Owner clarification; consistent with guardrails 2 and 3 and playbook s8. |
| 2026-11-03 | Three-day projection engine (`harabhara/state/projection.py`): stock by remaining life rolled forward under low/likely/high demand; shoppers take the freshest first (brief s2) as a configurable assumption; lot ages are inferred (the pack has no lot data). The same roll-forward will drive the replay. | Links stores, stock, shelf life, weather-driven demand into projected leftovers and shortages. |
| 2026-11-03 | Platform: sign-in is a PIN looked up in a JSON directory held in Secret Manager (`pin-directory`), returning an HMAC-signed 12-hour token (key in `session-signing-key`). If either secret is missing, sign-in answers 503 and data endpoints stay closed. Lists keep their contract body and carry staleness in an `X-Data-Stale` header. While the kill switch is on, proposed suggestions are hidden and decisions get 423. | Smallest scheme that scopes roles on a public URL without storing credentials in the repo; headers avoid changing `contracts.py`. |

## 4 Nov 2026: markdown ladder and buyer prices
- **Owner answer to question 8: yes**, a day-early start is allowed with approval. `earlier_start_allowed` is now true.
- **Why 15% a day early, 30% on the last day, 50% after 6 pm (greens and bananas only).** Cost is 50-65% of shelf price, so break-even is a 35-50% discount. 15% and 30% are above cost for all 25 products; 50% is below cost for 24 of 25 (tomato is exactly at cost). A smaller early cut earns more per unit (mango: Rs 74.8 at 15% against Rs 26.8 at 30%) if it still sells the stock. 50% stays as damage control, because binning loses the full cost.
- The early step uses only the promotion already in the data (`promo_pct_in_data`), and the guardrail refuses any other percentage for a day-early markdown. The purchase-cost floor applies to it as well.
- **Assumption:** the lift from a 15% cut is 0.30, the lowest measured in the 15% promotion rows (overall +42%). The 30% step reuses it, which is conservative.
- **Buyer prices.** Surplus suggestions now carry the buyer's price as a share of the shelf price and the result against cost, and the reason says so ("at 60% of the shelf price, Rs 12 below cost"). The best buyer beats cost on only 6 of 25 products, so a buyer is a loss-reducer for most. Limit: unit cost comes from purchase records; "best buyer" in the analysis ignored notice, capacity and distance, which the matcher does respect.
- Farmer screen: product names beside ids (P01 map added), and volumes are rounded to whole units.
| 2026-11-06 | Discounts: the 50% step (leafy greens, bananas) is proposed from `step_2_start_hour` (19:00), one hour after the 30% step, which on a below-cost product waits for 18:00. The playbook says the 50% step may start after 18:00, so 19:00 is allowed; `step_2_after_hour` still blocks anything earlier. 19:00 is an assumption for the owner to confirm. | The user chose different hours so the two steps are not one tile with the same time. |

## 12 Nov 2026: sample sign-ins on the login page (online trial)

The owner wants to show, on the public trial, who manages what. The login page now draws a small tree
(DC buying lead, then each area manager, then that area's stores, with the farmer group set to one side).
Each card shows its PIN and one tap signs in as that person.

- The PINs are not in the repo or the page. The server lists them at `GET /auth/demo` only when
  `HARABHARA_DEMO_LOGIN=1`; otherwise it answers 404 and the login page shows only the number pad.
- Terraform variable `demo_login` (default true for the trial) sets it. Set it to false for a real
  deployment, because anyone who opens the page can then sign in as anyone.
- Throttling of wrong PINs is unchanged. Guardrail 1 is untouched: signing in does not approve anything.
