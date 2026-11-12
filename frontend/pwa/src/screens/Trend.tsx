import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { HistorySeries, SeriesPoint, TalkPoint } from "../api/types";
import { Icon, type IconName } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Loading, LoadError } from "../components/Status";
import {
  productName,
  storeLabel,
  t,
  unitOf,
  type StringKey,
} from "../i18n/strings";
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

function dayLong(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
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

function summary(p: SeriesPoint): string {
  return p.products_closed === 0
    ? `${p.on}: ${t("trend.day.noCount")}`
    : `${p.on}: ${t("trend.waste")} ${pct(p.waste_pct)}, ${t("trend.out")} ${pct(p.stockout_pct)}`;
}

/**
 * Two lines on one chart, always together: thrown away (solid, round dots) and ran out (dashed,
 * square dots). Each day is a column you can hover, focus or tap to see what happened that day.
 */
export function Chart({
  data,
  active,
  onActive,
}: {
  data: HistorySeries;
  active: number;
  onActive: (i: number) => void;
}) {
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
  const step =
    pts.length <= 1 ? W : (W - PAD.left - PAD.right) / (pts.length - 1);
  const ticks = [0, top / 2, top];
  const labelAt = [0, Math.floor((pts.length - 1) / 2), pts.length - 1];
  const here = pts[active];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="group"
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
      {here && (
        <line
          x1={x(active)}
          x2={x(active)}
          y1={PAD.top}
          y2={H - PAD.bottom}
          className="trend-guide"
        />
      )}
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
              x={x(i) - (i === active ? 4.5 : 3)}
              y={y(p.stockout_pct) - (i === active ? 4.5 : 3)}
              width={i === active ? 9 : 6}
              height={i === active ? 9 : 6}
              className="trend-dot trend-out-dot"
            />
          )}
          {p.waste_pct !== null && (
            <circle
              cx={x(i)}
              cy={y(p.waste_pct)}
              r={i === active ? 5.5 : 3.5}
              className="trend-dot trend-waste-dot"
            />
          )}
        </g>
      ))}
      {pts.map((p, i) => (
        <rect
          key={`hit-${p.on}`}
          x={x(i) - step / 2}
          y={PAD.top}
          width={step}
          height={H - PAD.top - PAD.bottom}
          className="trend-hit"
          role="button"
          tabIndex={0}
          aria-label={summary(p)}
          aria-pressed={i === active}
          onMouseEnter={() => onActive(i)}
          onFocus={() => onActive(i)}
          onClick={() => onActive(i)}
        />
      ))}
    </svg>
  );
}

export function Names({
  rows,
  kind,
}: {
  rows: { sku_id: string; label: string }[];
  kind: "waste" | "out";
}) {
  return (
    <ul className="trend-names" data-kind={kind}>
      {rows.map((r) => (
        <li key={r.sku_id}>
          <ProductIcon skuId={r.sku_id} size={28} /> {r.label}
        </li>
      ))}
    </ul>
  );
}

/** What happened on the day under the finger or pointer, and where. */
export function DayDetail({
  p,
  onPick,
}: {
  p: SeriesPoint;
  onPick: (store: string) => void;
}) {
  return (
    <div
      className="trend-detail card"
      aria-live="polite"
      data-testid="trend-detail"
    >
      <h3>{dayLong(p.on)}</h3>
      {p.products_closed === 0 ? (
        <p className="notice">
          <Icon name="clock" size={20} /> {t("trend.day.noCount")}
        </p>
      ) : (
        <>
          <p>
            <strong>
              {t("trend.day.waste", {
                pct: pct(p.waste_pct),
                units: Math.round(p.units_wasted),
              })}
            </strong>
          </p>
          {p.top_waste.length > 0 && (
            <>
              <p className="small">{t("trend.day.topWaste")}</p>
              <Names
                kind="waste"
                rows={p.top_waste.map((w) => ({
                  sku_id: w.sku_id,
                  label: `${productName(w.sku_id)} · ${Math.round(w.units)} ${unitOf(w.sku_id)}`,
                }))}
              />
            </>
          )}
          <p>
            <strong>
              {t("trend.day.out", {
                pct: pct(p.stockout_pct),
                n: p.sold_out_products,
                m: p.products_closed,
              })}
            </strong>
          </p>
          {p.ran_out.length > 0 && (
            <>
              <p className="small">{t("trend.day.ranOut")}</p>
              <Names
                kind="out"
                rows={p.ran_out.map((r) => ({
                  sku_id: r.sku_id,
                  label:
                    r.stores > 1
                      ? t("trend.day.inStores", {
                          name: productName(r.sku_id),
                          n: r.stores,
                        })
                      : productName(r.sku_id),
                }))}
              />
            </>
          )}
        </>
      )}
      <p className="small">
        <Icon name="tick" size={18} />{" "}
        {t("trend.day.orders", {
          ok: p.orders_decided,
          late: p.orders_expired,
        })}
      </p>
      {p.by_store.length > 0 && (
        <>
          <p className="small">{t("trend.day.stores")}</p>
          <ul className="plain-list">
            {p.by_store.map((s) => (
              <li key={s.store_id}>
                <button
                  className="btn btn-plain decided-row"
                  style={{ width: "100%" }}
                  onClick={() => onPick(s.store_id)}
                >
                  <Icon name="store" size={20} />{" "}
                  {t("trend.day.store", {
                    store: storeLabel(s.store_id),
                    waste: pct(s.waste_pct),
                    out: pct(s.stockout_pct),
                  })}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

const TALK_ICON: Record<TalkPoint["code"], IconName> = {
  out_product: "crate",
  waste_product: "bag",
  store_out: "store",
  store_waste: "store",
  late_orders: "clock",
  no_counts: "calendar",
  out_rising: "alert",
  waste_rising: "alert",
  improving: "tick",
  all_fine: "tick",
};

function sentence(p: TalkPoint): { what: string; ask: string } {
  const sku = p.sku_id ? productName(p.sku_id) : "";
  const params = {
    sku,
    unit: p.sku_id ? unitOf(p.sku_id) : "",
    store: p.store_id ? storeLabel(p.store_id) : "",
    pct: pct(p.value ?? null),
    pts: String(Math.round(p.value ?? 0)),
    out: String(Math.round(p.value2 ?? 0)),
    n: String(p.n ?? 0),
    rows: String(Math.round(p.value2 ?? 0)),
    units: String(Math.round(p.value2 ?? 0)),
    orders: String(Math.round(p.value ?? 0)),
  };
  return {
    what: t(`talk.${p.code}` as StringKey, params),
    ask: t(`talk.${p.code}.ask` as StringKey),
  };
}

/** Things worth raising with a store manager, from the counts. Each is a question, not a verdict. */
function TalkList({
  talk,
  onPick,
}: {
  talk: TalkPoint[];
  onPick: (store: string) => void;
}) {
  if (talk.length === 0) return null;
  return (
    <section className="talk" aria-label={t("talk.title")} data-testid="talk">
      <h3>
        <Icon name="chat" size={24} /> {t("talk.title")}
      </h3>
      <p className="small">{t("talk.note")}</p>
      <ol className="stack">
        {talk.map((p, i) => {
          const s = sentence(p);
          return (
            <li
              key={`${p.code}-${p.sku_id ?? p.store_id ?? i}`}
              className="card talk-item"
              data-code={p.code}
            >
              <Icon name={TALK_ICON[p.code]} size={32} />
              <div>
                <p>
                  <strong>{s.what}</strong>
                </p>
                <p className="small">{s.ask}</p>
                {p.store_id && (
                  <button
                    className="btn btn-plain"
                    onClick={() => onPick(p.store_id as string)}
                  >
                    <Icon name="store" size={20} /> {t("talk.open")}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Weekly or monthly graph of waste and empty shelves, for the chain, the area, or one store. */
export function Trend({
  scope,
  onPick,
}: {
  scope: string;
  onPick: (store: string) => void;
}) {
  const [period, setPeriod] = useState<"week" | "month">("week");
  const [picked, setPicked] = useState<{ key: string; index: number } | null>(
    null,
  );
  const store = scope === "chain" ? undefined : scope;
  const { state, reload } = useLoad(
    () => api.historySeries(period, store),
    `${period}|${scope}`,
  );
  const key = `${period}|${scope}`;
  const active = picked?.key === key ? picked.index : null; // a new period or store starts fresh
  const data = state.status === "ready" ? state.data : null;
  // until a day is touched, show the latest day that has a count
  const latest = data
    ? Math.max(
        0,
        data.points.map((p) => p.products_closed > 0).lastIndexOf(true),
      )
    : 0;
  const shown = active ?? latest;
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
      {data && (
        <>
          <p>
            <strong>{data.scope_name}</strong>
          </p>
          {data.days_with_closing === 0 ? (
            <p className="notice">{t("trend.noData")}</p>
          ) : (
            <>
              <Chart
                data={data}
                active={shown}
                onActive={(index) => setPicked({ key, index })}
              />
              <p className="trend-legend">
                <span className="trend-key trend-key-waste" />{" "}
                {t("trend.waste")} <span className="trend-key trend-key-out" />{" "}
                {t("trend.out")}
              </p>
              <p className="small">{t("trend.hint")}</p>
              <p className="small">
                {t("trend.summary", {
                  waste: pct(data.waste_pct),
                  out: pct(data.stockout_pct),
                  n: data.days_with_closing,
                })}
              </p>
              <DayDetail p={data.points[shown]} onPick={onPick} />
              <TalkList talk={data.talk} onPick={onPick} />
            </>
          )}
          <p className="small">
            {data.farmer_share !== null
              ? t("trend.farmer", { share: pct(data.farmer_share * 100) })
              : t("trend.farmerUnknown")}
          </p>
        </>
      )}
    </section>
  );
}
