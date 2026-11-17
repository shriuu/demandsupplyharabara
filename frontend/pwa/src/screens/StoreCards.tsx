import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { StoreWeek } from "../api/types";
import { Icon } from "../components/Icons";
import { Loading, LoadError, TrafficLight } from "../components/Status";
import { storeLabel, t } from "../i18n/strings";
import { groupSteps } from "./priority";
import { pct } from "./StoreHistory";

type Light = "red" | "amber" | "green";

/** A day's light: red if shelves ran out on half the products, amber if anything did or waste is high. */
function dayLight(waste: number | null, out: number | null): "none" | "green" | "amber" | "red" {
  if (waste === null || out === null) return "none";
  if (out >= 50) return "red";
  if (out > 0 || waste >= 10) return "amber";
  return "green";
}

/** Compared with all stores, so no fixed limit is needed here. */
function storeLight(s: StoreWeek, allWaste: number | null, allOut: number | null): Light | null {
  if (s.waste_pct === null || s.stockout_pct === null || allWaste === null || allOut === null) return null;
  const wasteWorse = s.waste_pct > allWaste;
  const outWorse = s.stockout_pct > allOut;
  return wasteWorse && outWorse ? "red" : wasteWorse || outWorse ? "amber" : "green";
}

const rank: Record<Light, number> = { red: 0, amber: 1, green: 2 };

/**
 * The one way to pick a store: every store in the area side by side, worst first, with thrown away and
 * ran out together, a light against all stores, and a strip of the last seven days.
 */
export function StoreCards({ scope, onPick, allLabel }: { scope: string; onPick: (scope: string) => void; allLabel: string }) {
  const { state, reload } = useLoad(() => api.weekHistory(), []);
  // what is waiting for this person today: one card per product and store, as in the Decisions tab
  const queue = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const waitingBy = new Map<string, number>();
  if (queue.state.status === "ready") {
    const byStore = new Map<string, typeof queue.state.data>();
    for (const x of queue.state.data) byStore.set(x.store_id, [...(byStore.get(x.store_id) ?? []), x]);
    for (const [id, list] of byStore) waitingBy.set(id, groupSteps(list).length);
  }
  const { stores, chain_waste_pct, chain_stockout_pct } = state.data;
  const lit = stores.map((s) => ({ s, light: storeLight(s, chain_waste_pct, chain_stockout_pct), waiting: waitingBy.get(s.store_id) ?? 0 }));
  // today first: stores with something waiting for you, then the ones doing worse
  lit.sort((a, b) => b.waiting - a.waiting || (a.light ? rank[a.light] : 3) - (b.light ? rank[b.light] : 3));
  return (
    <section className="stack" aria-label={t("area.stores")} data-testid="store-cards">
      <p className="small">{t("area.storesNote")}</p>
      <ul className="tiles-2 store-cards">
        <li>
          <button className="card store-card" aria-pressed={scope === "chain"} onClick={() => onPick("chain")}>
            <h3>{allLabel}</h3>
            <p>
              <strong>{t("score.waste")} {pct(chain_waste_pct)}</strong> · <strong>{t("score.stockout")} {pct(chain_stockout_pct)}</strong>
            </p>
          </button>
        </li>
        {lit.map(({ s, light, waiting }) => (
          <li key={s.store_id}>
            <button className="card store-card" aria-pressed={scope === s.store_id} onClick={() => onPick(s.store_id)}>
              <h3>{storeLabel(s.store_id)}</h3>
              <p className={`store-wait ${waiting > 0 ? "store-wait-on" : ""}`} data-testid="store-waiting">
                <Icon name={waiting > 0 ? "clock" : "tick"} size={22} />{" "}
                {waiting > 0 ? t("area.cardWaiting", { n: waiting }) : t("area.cardNone")}
              </p>
              {s.days_with_closing === 0 ? (
                <p className="small">{t("week.noData")}</p>
              ) : (
                <>
                  {light && <TrafficLight light={light} />}
                  <p>
                    <strong>{t("score.waste")} {pct(s.waste_pct)}</strong> · <strong>{t("score.stockout")} {pct(s.stockout_pct)}</strong>
                  </p>
                </>
              )}
              <div className="week-strip" role="img" aria-label={t("week.title")}>
                {s.days.map((d) => (
                  <span
                    key={d.on}
                    className={`week-cell week-${dayLight(d.waste_pct, d.stockout_pct)}`}
                    title={t("week.dayTip", { day: d.on, waste: pct(d.waste_pct), out: pct(d.stockout_pct) })}
                  />
                ))}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
