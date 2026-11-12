import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import { Gauge } from "../components/Gauge";
import { Icon } from "../components/Icons";
import { Loading, LoadError } from "../components/Status";
import { productName, t, unitOf } from "../i18n/strings";
import { pct } from "./StoreHistory";
import { Chart, DayDetail, Names } from "./Trend";

/**
 * The store manager's own numbers: thrown away and ran out together (never one without the other),
 * the farmer-group share for all stores, how all stores did, and which products are behind it.
 */
export function MyNumbers() {
  const [period, setPeriod] = useState<"week" | "month">("week");
  const [picked, setPicked] = useState<{ key: string; index: number } | null>(null);
  const { state, reload } = useLoad(() => api.historySeries(period), period);
  const data = state.status === "ready" ? state.data : null;
  const latest = data ? Math.max(0, data.points.map((p) => p.products_closed > 0).lastIndexOf(true)) : 0;
  const shown = picked?.key === period ? picked.index : latest;
  return (
    <section className="stack" aria-label={t("numbers.title")} data-testid="my-numbers">
      <h2>
        <Icon name="chart" /> {t("numbers.title")}
      </h2>
      <div className="trend-toggle" role="group" aria-label={t("numbers.title")}>
        {(["week", "month"] as const).map((p) => (
          <button key={p} className={`btn nav-tile ${period === p ? "nav-on" : ""}`} aria-pressed={period === p} onClick={() => setPeriod(p)}>
            <Icon name="calendar" size={24} /> {t(p === "week" ? "trend.week" : "trend.month")}
          </button>
        ))}
      </div>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <LoadError onRetry={reload} />}
      {data && (
        <>
          <section className="card scoreboard">
            <div className="gauges">
              <Gauge label="score.waste" icon="bag" value={data.waste_pct} goodWhen="low" />
              <Gauge label="score.stockout" icon="box" value={data.stockout_pct} goodWhen="low" />
              <Gauge label="score.farmer" icon="tractor" value={data.farmer_share === null ? null : data.farmer_share * 100} goodWhen="high" />
            </div>
            <p className="small" data-testid="vs-all">
              {t("numbers.vsAll", { waste: pct(data.chain_waste_pct), out: pct(data.chain_stockout_pct) })}
            </p>
            <p className="small">{t("numbers.note")}</p>
          </section>
          {data.days_with_closing === 0 ? (
            <p className="notice">
              <Icon name="clock" size={20} /> {t("numbers.noCounts")}
            </p>
          ) : (
            <>
              <section className="card stack">
                <Chart data={data} active={shown} onActive={(index) => setPicked({ key: period, index })} />
                <p className="trend-legend">
                  <span className="trend-key trend-key-waste" /> {t("trend.waste")} <span className="trend-key trend-key-out" /> {t("trend.out")}
                </p>
                <p className="small">{t("numbers.pickDay")}</p>
                <DayDetail p={data.points[shown]} onPick={() => {}} />
              </section>
              <section className="card stack">
                {data.period_top_waste.length > 0 && (
                  <>
                    <h3>{t("numbers.wasteWhere")}</h3>
                    <Names kind="waste" rows={data.period_top_waste.map((w) => ({ sku_id: w.sku_id, label: `${productName(w.sku_id)} · ${Math.round(w.units)} ${unitOf(w.sku_id)}` }))} />
                  </>
                )}
                {data.period_ran_out.length > 0 && (
                  <>
                    <h3>{t("numbers.outWhere")}</h3>
                    <Names kind="out" rows={data.period_ran_out.map((r) => ({ sku_id: r.sku_id, label: `${productName(r.sku_id)} · ${t("numbers.times", { n: r.stores })}` }))} />
                  </>
                )}
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}
