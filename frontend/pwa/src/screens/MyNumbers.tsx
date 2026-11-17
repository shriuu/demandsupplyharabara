import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import { Icon } from "../components/Icons";
import { ThrownAwayAndRanOut } from "../components/Measure";
import { Loading, LoadError } from "../components/Status";
import { t } from "../i18n/strings";
import { ProductDashboard } from "./ProductDashboard";
import { StoreHistory } from "./StoreHistory";
import { Chart, DayDetail } from "./Trend";

/**
 * The store manager's own numbers: thrown away and ran out together (never one without the other),
 * each against its target and against all stores; the days on a graph; one tile for each product;
 * and a calendar to open any past day.
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
          <section className="card stack">
            <ThrownAwayAndRanOut waste={data.waste_pct} out={data.stockout_pct} allWaste={data.chain_waste_pct} allOut={data.chain_stockout_pct} />
            <p className="small">{t("measure.days", { n: data.days_with_closing })}</p>
          </section>
          {data.days_with_closing === 0 ? (
            <p className="notice">
              <Icon name="clock" size={20} /> {t("numbers.noCounts")}
            </p>
          ) : (
            <section className="card stack">
              <Chart data={data} active={shown} onActive={(index) => setPicked({ key: period, index })} />
              <p className="trend-legend">
                <span className="trend-key trend-key-waste" /> {t("trend.waste")} <span className="trend-key trend-key-out" /> {t("trend.out")}
              </p>
              <p className="small">{t("numbers.pickDay")}</p>
              <DayDetail p={data.points[shown]} onPick={() => {}} />
            </section>
          )}
          {data.days_with_closing > 0 && <ProductDashboard period="week" />}
        </>
      )}
      <StoreHistory />
    </section>
  );
}
