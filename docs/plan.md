# Plan to 12 November: what is done, what is not, day by day

Written 3 Nov 2026, 17:21 IST. This file is the checklist. If a chat message and this file
disagree, this file and the evidence it points to win. Update it at the end of each day.

## UPDATE 4 Nov, deadline moved to 6 Nov (this section wins over everything below)
| Day | Work | Done when |
|---|---|---|
| **4 Nov (done)** | Guardrail 4 module and test; matrix repointed to real tests; T04 scenario test; T03/T05 findings written; holdout script with a dry run | PR merged; `docs/scenarios_dev.md`; dry run output reviewed |
| **5 Nov (done 4 Nov)** | Feature freeze in the morning. Holdout read ONCE (`scripts/holdout_run.py --holdout`): T01, T03, T10 into `docs/final_results.md`. Business case, pilot plan, handover guide | `final_results.md` committed; lock file present |
| **6 Nov** | Go-live check on the live site as each role; handover walkthrough; ownership transfer | Live checks pass; new owner has the guide and the billing steps |

Done since 3 Nov: guardrail engine, reason writer, alerts, farmer forecast, pipeline, demo day loaded,
markdown ladder (owner Q8 yes), screens made clearer, driver ablation, this update.
Holdout read once on 4 Nov (`docs/final_results.md`); business case and pilot plan: `docs/business_case_and_pilot.md`; handover guide: `docs/handover.md`.
Still open: owner questions (lost-sale value, waste definition, deadline miss, farmer share definition),
chat assistant never called OpenAI, no mandi price feed, transfer distance not enforceable.
Cut for the new deadline (written for the next owner instead): voice, translations, offline mode, usability test,
shadow mode, LightGBM challenger, vendor draft messages.

---

## How to read it
- **Done and checked** means a test, a run output or a live check proves it. The evidence is named.
- **Built, not checked** means code exists but has not met the real thing.
- **Not started** means no code.
- A number appears here only if a script or test printed it. Where it comes from is named.

## Agreed scope and decisions (latest word wins)
| Decision | Source |
|---|---|
| Live on a public URL by **12 Nov**, then handover to another owner | owner, 3 Nov |
| Four role screens (store manager, area manager, DC lead, farmer coordinator), markdown timing, chat assistant | owner: not negotiable |
| Cloud is Google Cloud, Mumbai, project `agents-mu`, trial credit ends **28 Jan 2027** | ADR-0001 |
| Farmer commitments never reduced; only where the harvest goes can change (between stores, to surplus buyers). Mandi spot buying may be trimmed only as a suggestion | owner, 3 Nov; guardrails 2 and 3 |
| Incoming supply is committed; recommendations are the per-store order ask, how to split the committed supply, and the actions (markdown, transfer, surplus) | owner, 3 Nov |
| Weather does not change shelf life in this data; arrival temperature does. Any weather rule from the owner would be a labelled config rule | `docs/shelf_life.md` |
| Prices are not the focus. No data.gov.in key exists, so live mandi prices show "unavailable"; fallback is clearly labelled demo prices | owner, 3 Nov |
| Assistant uses OpenAI, behind an interface, and may only reword a stored suggestion | ADR-0005 |
| Voice, translations, offline mode, the 5-person usability study and a dev/staging/prod split are deferred, with a written plan for the next owner | ADR-0005 |
| The calendar holdout (6 Aug to 30 Sep) is read **once**, on 11 Nov | CLAUDE.md s10 |

## Status board (3 Nov, 17:21 IST)
### Done and checked
| What | Evidence |
|---|---|
| Repo, CI, typed config, rule/guardrail/test traceability | PR 1 and 2 merged; CI green on `main` |
| Data cleaning (25 duplicates, 120 blank waste, S07 outage) | `tests/data/test_clean.py` |
| Managers' rule reproduced: 23.6% and 28.7% error, 8.2% waste, 9.1% stock-outs | `tests/model/test_baselines_metrics.py` |
| Hidden demand on sold-out days: about 1.9% of units | `docs/hidden_demand.md` |
| Shelf-life model: off by 0.62 days vs 0.83 for the rule on unseen dates; T09 passes | `docs/shelf_life.md` |
| Demand forecast, development windows only: 19.3% vs 22.4% and 20.3% vs 23.0% error | `docs/demand_forecast.md` |
| Stock simulator reproduces recorded waste: 8.17% vs 8.00% | `docs/simulator.md` |
| Replay, development window: same supply, our split: waste 7.77% to 7.33%, stock-outs 10.49% to 9.01%. With spot trimming and a 0.925 floor: 5.62% and 7.03% | `docs/replay.md` |
| Markdown, surplus matching, transfers; T07 and T08 pass | `tests/rules/`, `tests/scenarios/` |
| Platform API, PIN sign-in, approvals, audit log, kill switch; frontend for four roles; browser tests against the real API | merged PRs; 386 tests passed at the last full run |
| Infrastructure applied (28 resources); first deploy succeeded; wrong PIN returns 401; data needs sign-in | GitHub Actions run, live checks |

### Built, not checked against the real thing
- The chat assistant has never called OpenAI (the key is stored and mounted now).
- Live price client: never saw a real response; no key.
- Real people have not signed in on the live site yet.

### Not started
- **Guardrail engine** (`harabhara/rules/` is empty) and its property tests: 27 of 42 matrix rows are still planned.
- **Reason writer** (`harabhara/reasons/` is empty): every suggestion needs a one-sentence reason (guardrail 9).
- **Alert logic** tying projection, markdown, transfer and surplus into suggestions.
- **Farmer-group volume forecast** (`decisions/farmer_volumes.py` does not exist) and the DC totals and trimming data.
- **Pipeline** that writes all of the above for the API, and loading it into Firestore. The live screens are empty until this runs.
- Robustness runs (noisy weather, no weather), the LightGBM challenger, range calibration by horizon, tomato investigation.
- Holdout run (T01), full replay by store and category (T10), scenarios T02 to T06.
- Business case, pilot plan, handover guide.

## Day by day
| Date | Work | Done when |
|---|---|---|
| **3 Nov (today)** | Foundations, models, replay, actions, platform, frontend, infrastructure, first deploy | Table above |
| **4 Nov** | Guardrail engine, tests first (G01 to G12, PB rules as property tests). Reason writer. Alert logic producing `Suggestion` objects | Every suggestion passes the engine; none without a reason; matrix rows move to implemented only with a test |
| **5 Nov** | Pipeline v1 for an as-of date inside the training period. Load into Firestore. Check each role's screen on the live site | You sign in as each role and see real content |
| **6 Nov** | Farmer-group volume forecast, DC totals, spot-first trimming, scorecard (waste, stock-outs, farmer share always together) | DC and farmer screens show data; farmer volume never reduced (test) |
| **7 Nov** | Robustness: noisy weather, no weather. Range calibration by horizon and category. LightGBM challenger. Tomato check | Numbers written in `docs/demand_forecast.md`, including losses |
| **8 Nov** | Assistant tested with the real key (grounding, injection). Demo-price fallback. Failure tests (feed down, storage down). Terraform state to a bucket (needs your yes) | Assistant answers from a stored suggestion and says "I don't have that" otherwise |
| **9 Nov** | Frontend polish. Informal test with whoever you can get. Scenario tests T02 to T06 scaffolded. Handover guide drafted | Draft handover guide in `docs/` |
| **10 Nov** | **Feature freeze.** Integration, full tests, deploy. Freeze config and model version. Dry-run the holdout script on a development window | Frozen versions written down; CI green; live site healthy |
| **11 Nov** | **Holdout read once.** T01 (error and bias by category and store), T10 (replay by store and category), T02 to T09. Business case and pilot plan. Then load holdout-date demo data | Honest results in `docs/final_results.md`, misses included |
| **12 Nov** | Buffer. Go-live check. Handover walkthrough and ownership transfer | New owner can sign in, deploy and read the docs |

## Needed from you, with dates
| By | What |
|---|---|
| Now | Sign in on the live site with each role's PIN and tell me if any fails |
| 4 Nov | Answer: early markdowns allowed as approval-needed suggestions? (assumed yes) |
| 5 Nov | Who receives the handover (GitHub username, email) and which cloud they know |
| 5 Nov | Approve the wording changes to `CLAUDE.md` (guardrail 3, repo layout) |
| 8 Nov | Yes or no on moving Terraform state to a Cloud Storage bucket |
| Before 12 Nov | Turn on branch protection for `main`; decide about the broad "Agents-mu" API key |
| Optional | A data.gov.in key; real answers on lost-sale value and farmer share |

## Risks and limits I will not hide
- The 19% error target is **not shown to be met**; development windows were 19.3% and 20.3%.
- Replay numbers so far are from a window inside the training period, and the service floor was tuned on it. Treat them as optimistic until 11 Nov.
- Replay assumptions: demand does not react to shelf stock; lots start with the grade-A shelf life; weather in the forecast is the observed value. Leafy-greens stock-out levels are unreliable.
- The Terraform state file exists only on one Mac until it is moved.
- The trial credit ends 28 Jan 2027; the new owner must attach their own billing before then.
- Nine days is tight; if something slips, the cut order is: usability test, robustness extras, then polish. Guardrails, the holdout run and the handover guide do not get cut.

## Rules I follow so this stays honest
1. No number in a report unless a script or test printed it.
2. "Done" requires a test, a run or a live check, named here.
3. Holdout: read once, on 11 Nov.
4. Nothing in the cloud changes without your yes after I show the plan.
5. No keys, PINs or personal details in chat or in the repo.
6. Every assumption is labelled as one, in config and in the docs.
