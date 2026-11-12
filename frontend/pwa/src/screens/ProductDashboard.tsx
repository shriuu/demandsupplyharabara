import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { ProductSeries } from "../api/types";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Loading, LoadError } from "../components/Status";
import { productName, t, unitOf } from "../i18n/strings";
import { pct } from "./StoreHistory";

const W = 320;
const H = 150;
const PAD = { left: 34, right: 8, top: 10, bottom: 24 };

const dayShort = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const num = (v: number | null) => (v === null ? "–" : String(Math.round(v)));

/** Two bars a day: what was left on the shelf (green) and what was thrown away (amber); a red square on a day it ran out. */
function Bars({ p }: { p: ProductSeries }) {
  const top = Math.max(10, ...p.days.flatMap((d) => [d.units_left ?? 0, d.units_wasted ?? 0]));
  const span = W - PAD.left - PAD.right;
  const slot = span / p.days.length;
  const bar = Math.max(2, Math.min(14, slot / 2 - 1));
  const y = (v: number) => PAD.top + (1 - v / top) * (H - PAD.top - PAD.bottom);
  const base = H - PAD.bottom;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("numbers.d.chart", { product: productName(p.sku_id) })} className="trend-svg">
      {[0, top / 2, top].map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="trend-grid" />
          <text x={PAD.left - 4} y={y(v) + 4} textAnchor="end" className="trend-axis">{Math.round(v)}</text>
        </g>
      ))}
      {p.days.map((d, i) => {
        const cx = PAD.left + slot * i + slot / 2;
        return (
          <g key={d.on}>
            {d.units_left !== null && <rect x={cx - bar - 0.5} y={y(d.units_left)} width={bar} height={Math.max(0, base - y(d.units_left))} className="bar-left" />}
            {d.units_wasted !== null && <rect x={cx + 0.5} y={y(d.units_wasted)} width={bar} height={Math.max(0, base - y(d.units_wasted))} className="bar-wasted" />}
            {d.sold_out && <rect x={cx - 3} y={PAD.top - 6} width={6} height={6} className="trend-out-dot" />}
          </g>
        );
      })}
      {[0, Math.floor((p.days.length - 1) / 2), p.days.length - 1].map((i) => (
        <text key={i} x={PAD.left + slot * i + slot / 2} y={H - 6} textAnchor={i === 0 ? "start" : i === p.days.length - 1 ? "end" : "middle"} className="trend-axis">
          {dayShort(p.days[i].on)}
        </text>
      ))}
    </svg>
  );
}

function Detail({ p, onBack }: { p: ProductSeries; onBack: () => void }) {
  const unit = unitOf(p.sku_id);
  return (
    <article className="card stack" data-testid="product-detail">
      <button className="btn btn-plain" onClick={onBack}>
        <Icon name="back" size={28} /> {t("numbers.back")}
      </button>
      <div className="product">
        <ProductIcon skuId={p.sku_id} size={72} />
        <h3>{productName(p.sku_id)}</h3>
      </div>
      <p>
        <strong>{t("numbers.d.summary", { sold: Math.round(p.units_sold), wasted: Math.round(p.units_wasted), pct: pct(p.waste_pct), ran: p.days_ran_out, days: p.days_counted })}</strong>
      </p>
      <Bars p={p} />
      <p className="trend-legend">
        <span className="key-box bar-left" /> {t("numbers.d.keyLeft")} <span className="key-box bar-wasted" /> {t("numbers.d.keyWasted")} <span className="key-box trend-out-dot" /> {t("numbers.d.keyRan")}
      </p>
      <table className="day-table">
        <thead>
          <tr>
            <th>{t("numbers.d.day")}</th>
            <th>{t("numbers.d.sold")}</th>
            <th>{t("numbers.d.left")}</th>
            <th>{t("numbers.d.wasted")}</th>
            <th>{t("numbers.d.ran")}</th>
          </tr>
        </thead>
        <tbody>
          {[...p.days].reverse().map((d) => (
            <tr key={d.on} data-counted={d.units_sold !== null}>
              <td>{dayShort(d.on)}</td>
              {d.units_sold === null ? (
                <td colSpan={4} className="small">{t("numbers.d.notCounted")}</td>
              ) : (
                <>
                  <td>{num(d.units_sold)}</td>
                  <td>{num(d.units_left)}</td>
                  <td>{num(d.units_wasted)}</td>
                  <td>{d.sold_out ? <Icon name="stop" size={18} /> : ""}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="small">{unit}</p>
    </article>
  );
}

/** A tile for every product, with its own numbers; tap one to see every day. Waste and leftover side by side. */
export function ProductDashboard({ period }: { period: "week" | "month" }) {
  const { state, reload } = useLoad(() => api.productHistory(period), period);
  const [open, setOpen] = useState<string | null>(null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const products = state.data.products;
  if (!products.length) return null;
  const chosen = products.find((p) => p.sku_id === open);
  if (chosen) return <Detail p={chosen} onBack={() => setOpen(null)} />;
  return (
    <section className="stack" aria-label={t("numbers.products")} data-testid="product-tiles">
      <h3>{t("numbers.products")}</h3>
      <p className="small">{t("numbers.productsHint")}</p>
      <ul className="tiles">
        {products.map((p) => (
          <li key={p.sku_id}>
            <button className="btn tile" style={{ width: "100%" }} onClick={() => setOpen(p.sku_id)}>
              <ProductIcon skuId={p.sku_id} size={56} />
              <span className="tile-name">{productName(p.sku_id)}</span>
              <span className="tile-amount">{t("numbers.tileWaste", { n: Math.round(p.units_wasted), unit: unitOf(p.sku_id) })}</span>
              <span className="tile-amount">
                {p.average_left === null ? t("numbers.tileNoLeft") : t("numbers.tileLeft", { n: Math.round(p.average_left), unit: unitOf(p.sku_id) })}
              </span>
              {p.days_ran_out > 0 && (
                <span className="tile-amount ran-out">
                  <Icon name="stop" size={16} /> {t("numbers.tileRan", { n: p.days_ran_out })}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
