# Owner questions: what the documents already answer

Status key: **Answered** = playbook or brief settles it (we follow that). **Partly** = there is a direction but no value or definition. **Open** = we need the owner.

| # | Question (CLAUDE.md §16) | Status | What the docs say | Blocks |
|---|---|---|---|---|
| 1 | Manager doesn't respond by the ordering deadline? | **Open** | Nothing. CLAUDE.md says the suggestion expires and nothing new happens. That means the store gets no order. Owner must say whether it falls back to yesterday's order, the suggestion or nothing. | workflow/deadlines |
| 2 | Who approves when the area manager is absent? | **Open** | Playbook §13 names only the area manager (transfers, and markdowns on >30% of a delivery). | workflow/approvals |
| 3 | Is trimming spot buying before FPO buying allowed? | **Partly** | §8 forbids cancelling a confirmed order after harvest and timing purchases against FPOs. It doesn't say spot-first trimming is allowed, but it is the only option that doesn't break §8. | decisions/farmer_volumes, DC screen |
| 4 | What counts as waste? | **Partly** | §11: "units binned ÷ units received". So markdown and surplus-sold units are *not* waste. Donation is not stated. | metrics, costs |
| 5 | What is one lost sale worth, including the basket? | **Partly** | §2 and §12 say a tomato or coriander stock-out "loses the customer's whole basket", but give no value. | order rule cost ratio |
| 6 | Can stores record lot or arrival age? | **Partly** | The DC records `days_since_harvest_at_receipt` and grade per purchase. Sales data has **no lot, age or grade per store-day**. The ledger must infer age (FIFO from delivery dates). | state/stock_ledger |
| 7 | Where does the weather forecast come from? | **Open** | Data has observed weather from one station only. We'll train on actuals plus noise to imitate a forecast. A live source is undecided. | features/weather, deployment |
| 8 | Can discounts start before the last day, using only existing steps? | **Partly** | §5 says it is "what we want", but the current rule is last day only. Brief lists optimised markdown timing as a stretch goal. | decisions/discount |
| 9 | How are one-off shocks reported? | **Open** | Only the S07 outage is documented, in the README. | data/validate |
| 10 | How often can the FPO forecast change, and how is it labelled? | **Partly** | §8: a three-day forecast is shared and confirmed orders can't be cancelled. No refresh cadence. | farmer screen |
| 11 | Food-safety or recall procedure? | **Open** | Nothing beyond grading, storage and the chilling-injury rule. | rules/guardrails #8 |
| 12 | Languages and voice input? | **Open** | Not mentioned. | frontend |
| 13 | How does the replay treat extra stock, discount response and product swaps? | **Open** | Brief: "replay with the playbook's shelf-life and markdown rules". No demand-response model is given. Our assumption is that demand is fixed and equals estimated true demand. | sim/ |

## New questions raised by the data

| # | Question | Why it matters |
|---|---|---|
| 14 | The QC data shows produce **lasting longer than the rule on 20% of samples** (rule MAE 0.85 days, rule overstates on average +0.4 d). Guardrail 6 says the rule always wins. Is that still right when FPO produce arrives fresh (harvested on day 0 or 1)? | Capping at the rule can only shorten life, which will stop us cutting waste on fresh FPO lots |
| 15 | **Stores have no coordinates or distances.** Which store pairs are within the 6 km transfer limit? | T7 and every transfer suggestion depend on this. Fallback: the 132 store pairs that already appear in logged transfers |
| 16 | **How should "farmer share" be defined?** Options: (a) FPO volume ÷ total volume per product vs `target_share_of_volume`, (b) ₹ paid to FPOs, (c) FPO volume vs the forecast shared with them. Today FPO share is 0.35–0.38 for every product, below the target for FPO-02, 07 and 08 (0.49–0.54) | Third headline measure; needed before any replay result is reported |
| 17 | What does "low-value product" mean for the 20-unit transfer rule? | rules.yaml transfer.low_value_threshold_inr |
| 18 | Does grade-C mandi produce (7.5% of mandi lots) reach store shelves today? Sales data carries no grade | Guardrail 5 can't be checked historically |
| 19 | Is the target for each forecast "units sold" or "demand"? The brief measures WAPE against **sold**, which is censored. | We will report both, but only one headline |
