# Why this model, how it was trained, what it can and cannot do

Written for the demo and for the owner's questions. Every number here comes from the project's own documents (final_results.md, demand_forecast.md, shelf_life.md, hidden_demand.md, simulator.md, replay.md). Nothing is added from memory.

## 1. What we built, in plain words

Each evening the tool suggests how much each store should order. Each morning it warns about produce likely to be left over and produce likely to sell out, and suggests a discount, a move between stores, or a sale to a surplus buyer. A person approves every action. Nothing is ordered, priced or moved by the tool on its own.

Behind that sit three pieces. A demand model that forecasts a low, likely and high number of units for every store and product, one to three days ahead. A shelf life model that says how many days each delivery will stay sellable. A set of fixed rules from the owner's playbook that block anything not allowed, such as paying farmer groups below their floor, selling past the last sellable day, or putting grade C produce on a full price shelf.

## 2. Why this kind of model

We looked at the options and chose the simplest one that handles many drivers at once.

The managers' own rule ignores weather, festivals, price and stock age, so it is only our baseline. A separate statistical model for each store and product cannot share what it learns across stores and products, and copes badly with new items. Deep learning networks need far more data than a few months of sales for 25 products, and are hard to explain to a store manager. Rules alone cannot learn the effect of rain or a festival, but rules are exactly right for the safety limits, so we kept rules for those.

What we chose is one gradient boosted tree model (CatBoost) for every store and product together. It uses weather, weekday, festival, price, stock and store type at the same time. It learns across stores, so a new store or a thin product is not left on its own. It works well on data of this size, runs fast, and every forecast can be explained by its real drivers. It gives a range, not just one number, which is what an order decision needs.

The order itself is not a black box. It follows a simple rule: order up to the point in the forecast range where one more wasted unit costs about as much as one more lost sale, counting only stock that will still be sellable. A manager can follow that.

## 3. How we trained it, and how we avoided cheating

Clean the data first. Remove exact duplicates, rebuild blank waste values from stock arithmetic, and exclude the days one store's till was down, so they do not teach the model that demand was zero.

Fix what sold out days hide. When a product sells out, recorded sales understate demand. We estimate the missed demand from the hour it sold out and train on that estimate, and keep a flag on those rows so every accuracy check uses only honest, non sold out days. Overall the hidden amount is small, 1.9% of units, but it is larger for fast sellers on weekends and festival eves.

Use only what was known the evening before. Every input is built as of the forecast evening: recent sales, the same weekday in earlier weeks, the target day's weekday, payday, school holiday and festival, weather, shelf and mandi price, store details. A test changes every sales, price and stock figure after the forecast day and checks that no input moves.

Split by time, not at random. The model was fitted on history before each test window and scored on the window after it. The final test period (6 Aug to 30 Sep 2026) was read once at the end, and the script refuses a second read.

Beat the baseline on the same rows. The managers' rule was rebuilt exactly as the playbook describes and reproduces the brief's 23.6% forecast error. The model has to beat it row for row.

Make the range honest. The low to high range is adjusted on a recent window so it holds about 80% of outcomes. This is slightly short: it held 79.2% and 77.8% in the two validation windows, and 82.2% on the final test.

Shelf life model. Trained on the quality checks at delivery: days since harvest, arrival temperature, firmness, colour, defects, grade, source and product. It gives days left with a range. Its answer is never allowed to exceed the playbook's last sellable day. On quality checks it had never seen, its error was 0.62 days against 0.85 for the fixed rule.

Prove the simulator before trusting it. The replay that estimates waste and empty shelves was first fed the managers' real deliveries. It reproduced their real waste within half a point (8.17% against 8.00%) in the training period. Only then were replay results used.

## 4. What the final test showed

Final test, 6 Aug to 30 Sep 2026, read once. Managers' column is a simulation of their splits.

Forecast error: 23.6% for the managers, 19.5% for the model, on the same 14,784 rows. Bias is small, minus 0.6%.
Waste: 9.46% down to 5.76%.
Empty shelves: 8.68% down to 6.00%.
Gross margin: 35.63% up to 37.47%.
Farmer group share of supply: 31.8% up to 32.9%. Confirmed farmer volume was never cut.

Waste and empty shelves fell together, so one did not buy the other. Two targets are missed and we say so: waste 5.76% is above the 5.5% target, and forecast error 19.5% is above the 19% target. Empty shelves at 6.00% are under the 7% ideal.

## 5. The benefits

Less waste without emptier shelves, measured together. A forecast that is wrong less often and has a range instead of a guess. Weekends, rain and festivals planned for, with a different festival lift per product instead of one flat bump. Early warnings each morning with the action already worked out. Shelf life that follows the actual produce, not a fixed rule. Surplus matched to buyers whose notice and pickup windows can be met. Farmer groups not worse off: the tool never cuts confirmed volume and trims spot buying first, as a suggestion only. Every suggestion carries one sentence a store manager would say, and every decision, edit and reason is recorded.

## 6. The limitations, plainly

The results are a replay, not real orders. The managers' column is a simulation. It assumes demand does not change when stock is higher or a markdown is on. It uses one data pack. The tool has not yet run in a real store.

The simulator is not perfect. Its waste matches history, but for leafy greens it shows empty shelves twice as high as recorded (8.2% against 4.2%), so for greens only the change is reliable, not the level.

Two targets are missed on the final test, waste (5.76% against 5.5%) and forecast error (19.5% against 19%).

Sold out days are estimated, not observed. The estimate assumes sales are spread evenly through the day. If most sell early or late, the estimate is off by up to about 9% on those rows only. Hourly sales from even one store would replace the assumption with a measurement.

New seasons and new products are weak. When a seasonal fruit has not been seen, the model falls back to a recent average that only matches the managers' rule, it does not beat it. A second season of a known product could not be tested with one season of data.

Some products are still off. Tomato was over forecast by 13.5% in the summer window and the cause was not established. Festival lift is under forecast for bananas and coconut on the final test (1.16 times against 1.29 times for Robusta banana). Leafy greens gain least on empty shelves, 0.26 points.

Weather was the observed value, standing in for a forecast. A real forecast is noisier, so results are somewhat optimistic. A live weather source has not been chosen. The tests with weather removed or noisy, and with prices blank, are still to do.

Settings were not carefully tuned and the second model (LightGBM) was not built as a challenger. The service level floor of 0.925 was tuned on training data, not on the final test.

The shelf life model is capped by the playbook rule, which costs a little accuracy: the model wants to go above the rule for 43% of samples. Its range is not yet calibrated. It rounds down to whole days, so some produce is marked as short lived a day early.

The value of a lost sale is a placeholder until the owner sets it. Margin is gross margin on this data, not a signed off profit figure.

The tool does not yet learn from the outcomes people record. Outcomes are stored, but forecasts are not yet retrained from them on a schedule with drift checks.

Mandi prices are not live. The data feed is built but has never been confirmed against a real answer, and needs a key from data.gov.in. For now the screens show no price rather than a guess.

No usability test has been done with people who cannot read the interface language, and shadow mode and a pilot with comparison stores have not been run.

Several owner decisions are still open: what happens when a manager misses the order deadline, who approves when the area manager is absent, the exact definition of waste and of farmer share, the recall procedure, and which languages the screens need.

## 7. Why can someone not simply build this for the owner

Honest answer: someone can. A good team could build a forecasting model and show similar numbers in a few weeks. The model itself is not the hard part, and we should not claim it is. What is hard is everything around it, and some of that is already done here.

The owner's rules are built in as tested code, not as advice. Farmer floors, confirmed volumes never reduced, no grade C on full price shelves, nothing sold past the last sellable day, discount, transfer and surplus limits. Each has a test that must always pass. A generic tool would not know them.

The sold out correction. Most forecasting tools train on recorded sales and quietly learn that demand is lower than it is. Fixing this, and keeping honest rows apart for scoring, is what stops the tool from cutting waste by emptying shelves.

The simulator proven against history. Anyone can claim a waste cut. Here the replay was first shown to reproduce the managers' real waste before any result was trusted, and the final test was read once.

The three measures always shown together. Waste, empty shelves and farmer share can never be reported alone, so a gain on one cannot hide a loss on another.

People stay in charge, and it is recorded. Approve, edit with a reason, reject, deadlines, an append only audit trail, a kill switch, and a safe fallback when data or the model fails. Four screens designed for people who may not read, each seeing only their own store or area.

What is truly hard to copy is not in the code. It is the owner's own data over time, the real decisions managers make and why, and the closed loop of outcomes back into the forecasts. That loop is the part still to be built. So the honest position is: the foundations and the safety are built and tested, the proof is a replay, and the lasting advantage only comes from running it in real stores with the owner's data and learning from it.

## 8. What would make it stronger next

Run in shadow mode first, with suggestions hidden, and compare with what managers did. Then a small pilot with comparison stores. Get the lost sale value and the waste definition from the owner. Connect a real weather forecast and confirm the mandi price feed with a key. Add the weather noise and missing price tests. Retrain on a schedule from recorded outcomes with drift checks. Ask for hourly sales from one store to replace the sold out assumption. Test the evening order with people who cannot read the interface language.
