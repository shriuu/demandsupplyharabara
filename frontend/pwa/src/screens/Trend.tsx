import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { HistorySeries, SeriesPoint } from "../api/types";
import { Icon } from "../components/Icons";
import { Loading, LoadError } from "../components/Status";
import { t } from "../i18n/strings";
import { pct } from "./StoreHistory";

const W = 320;
const H = 170;
const PAD = { left: 34, right: 10, top: 12, bottom: 26 };

function dayShort(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}

/** Segments of consecutive days that have a value, so a day nobody closed is a gap, never a zero. */
function segments(
  points: SeriesPoint[],
  pick: (p: SeriesPoint) => number | null,
  x: (i: number) => number,
  y: (v: number) => number,
): string[] {
  const out: string[] = [];
  let run: string[] = [];
  points.forEach((p, i) => {
    const v = pick(p);
    if (v === null) {
      if (run.length) out.push(run.join(" "));
      run = [];
    } else run.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  });
  if (run.length) out.push(run.join(" "));
  return out;
}

/** Two lines on one chart, always together: thrown away (solid, round dots) and ran out (dashed, square dots). */
function Chart({ data }: { data: HistorySeries }) {
  const pts = data.points;
  const top = Math.max(
    10,
    Math.ceil(
      Math.max(
        0,
        ...pts.flatMap((p) => [p.waste_pct ?? 0, p.stockout_pct ?? 0]),
      ) / 10,
    ) * 10,
  );
  const x = (i: number) =>
    PAD.left +
    (pts.length <= 1 ? 0 : (i * (W - PAD.left - PAD.right)) / (pts.length - 1));
  const y = (v: number) => PAD.top + (1 - v / top) * (H - PAD.top - PAD.bottom);
  const ticks = [0, top / 2, top];
  const labelAt = [0, Math.floor((pts.length - 1) / 2), pts.length - 1];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={t("trend.chart", { from: data.start, to: data.end })}
      className="trend-svg"
    >
      {ticks.map((v) => (
        <g key={v}>
          <line
            x1={PAD.left}
            x2={W - PAD.right}
            y1={y(v)}
            y2={y(v)}
            className="trend-grid"
          />
          <text
            x={PAD.left - 4}
            y={y(v) + 4}
            textAnchor="end"
            className="trend-axis"
          >{`${v}%`}</text>
        </g>
      ))}
      {labelAt.map((i) => (
        <text
          key={i}
          x={x(i)}
          y={H - 6}
          textAnchor={
            i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"
          }
          className="trend-axis"
        >
          {dayShort(pts[i].on)}
        </text>
      ))}
      {segments(pts, (p) => p.stockout_pct, x, y).map((d, i) => (
        <polyline key={`o${i}`} points={d} className="trend-line trend-out" />
      ))}
      {segments(pts, (p) => p.waste_pct, x, y).map((d, i) => (
        <polyline key={`w${i}`} points={d} className="trend-line trend-waste" />
      ))}
      {pts.map((p, i) => (
        <g key={p.on}>
          {p.stockout_pct !== null && (
            <rect
              x={x(i) - 3}
              y={y(p.stockout_pct) - 3}
              width={6}
              height={6}
              className="trend-dot trend-out-dot"
            >
              <title>{`${p.on}: ${t("trend.out")} ${pct(p.stockout_pct)}`}</title>
            </rect>
          )}
          {p.waste_pct !== null && (
            <circle
              cx={x(i)}
              cy={y(p.waste_pct)}
              r={3.5}
              className="trend-dot trend-waste-dot"
            >
              <title>{`${p.on}: ${t("trend.waste")} ${pct(p.waste_pct)}`}</title>
            </circle>
          )}
        </g>
      ))}
    </svg>
  );
}

/** Weekly or monthly graph of waste and empty shelves, for the chain, the area, or one store. */
export function Trend({ scope }: { scope: string }) {
  const [period, setPeriod] = useState<"week" | "month">("week");
  const store = scope === "chain" ? undefined : scope;
  const { state, reload } = useLoad(
    () => api.historySeries(period, store),
    `${period}|${scope}`,
  );
  return (
    <section
      className="card stack"
      aria-label={t("trend.title")}
      data-testid="trend"
    >
      <h2>
        <Icon name="chart" /> {t("trend.title")}
      </h2>
      <div className="trend-toggle" role="group" aria-label={t("trend.title")}>
        {(["week", "month"] as const).map((p) => (
          <button
            key={p}
            className={`btn nav-tile ${period === p ? "nav-on" : ""}`}
            aria-pressed={period === p}
            onClick={() => setPeriod(p)}
          >
            <Icon name="calendar" size={24} />{" "}
            {t(p === "week" ? "trend.week" : "trend.month")}
          </button>
        ))}
      </div>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <LoadError onRetry={reload} />}
      {state.status === "ready" && (
        <>
          <p>
            <strong>{state.data.scope_name}</strong>
          </p>
          {state.data.days_with_closing === 0 ? (
            <p className="notice">{t("trend.noData")}</p>
          ) : (
            <>
              <Chart data={state.data} />
              <p className="trend-legend">
                <span className="trend-key trend-key-waste" />{" "}
                {t("trend.waste")} <span className="trend-key trend-key-out" />{" "}
                {t("trend.out")}
              </p>
              <p className="small">
                {t("trend.summary", {
                  waste: pct(state.data.waste_pct),
                  out: pct(state.data.stockout_pct),
                  n: state.data.days_with_closing,
                })}
              </p>
            </>
          )}
          <p className="small">
            {state.data.farmer_share !== null
              ? t("trend.farmer", { share: pct(state.data.farmer_share * 100) })
              : t("trend.farmerUnknown")}
          </p>
        </>
      )}
    </section>
  );
}
