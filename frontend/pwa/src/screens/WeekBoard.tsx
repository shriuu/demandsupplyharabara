import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import { Icon } from "../components/Icons";
import { Loading, LoadError } from "../components/Status";
import { storeLabel, t } from "../i18n/strings";
import { pct } from "./StoreHistory";

/** A day's light: red if shelves ran out on half the products, amber if anything did or waste is high. */
function dayLight(waste: number | null, out: number | null): "none" | "green" | "amber" | "red" {
  if (waste === null || out === null) return "none";
  if (out >= 50) return "red";
  if (out > 0 || waste >= 10) return "amber";
  return "green";
}

/** Store-by-store dashboards for the last seven days. Waste and empty shelves always sit together. */
export function WeekBoard({ onPick }: { onPick: (store: string) => void }) {
  const { state, reload } = useLoad(() => api.weekHistory(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const { stores, farmer_share, farmer_share_definition } = state.data;
  return (
    <section className="stack" aria-label={t("week.title")}>
      <h2>
        <Icon name="calendar" /> {t("week.title")}
      </h2>
      <p className="small">{t("week.note")}</p>
      <p className="small">
        {farmer_share !== null
          ? t("week.farmer", { share: pct(farmer_share * 100) })
          : t("week.farmerUnknown", { why: farmer_share_definition ?? "" })}
      </p>
      <ul className="tiles-2">
        {stores.map((s) => (
          <li key={s.store_id} className="card">
            <button className="btn btn-plain" style={{ width: "100%", flexDirection: "column" }} onClick={() => onPick(s.store_id)}>
              <h3>{storeLabel(s.store_id)}</h3>
              {s.days_with_closing === 0 ? (
                <p className="small">{t("week.noData")}</p>
              ) : (
                <p>
                  <strong>{t("week.waste")} {pct(s.waste_pct)}</strong> · <strong>{t("week.out")} {pct(s.stockout_pct)}</strong>
                </p>
              )}
              <p className="small">{t("week.closedDays", { n: s.days_with_closing })}</p>
              <p className="small">{t("week.decided", { ok: s.orders_decided, late: s.orders_expired })}</p>
              <div className="week-strip" role="img" aria-label={t("week.title")}>
                {s.days.map((d) => {
                  const light = dayLight(d.waste_pct, d.stockout_pct);
                  return (
                    <span
                      key={d.on}
                      className={`week-cell week-${light}`}
                      title={t("week.dayTip", { day: d.on, waste: pct(d.waste_pct), out: pct(d.stockout_pct) })}
                    />
                  );
                })}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
