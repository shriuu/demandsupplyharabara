import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { DcOrders, PriceQuote } from "../api/types";
import { Counter } from "../components/Counter";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { RangeBar } from "../components/RangeBar";
import { Empty, Loading, LoadError, TrafficLight } from "../components/Status";
import { ENTRY_STEP_UNITS } from "../config";
import { todayIso } from "../dates";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";

/** Never shows a number for an unavailable price (guardrails 11, 12). */
export function PriceCard({ quote }: { quote: PriceQuote }) {
  const light = quote.status === "ok" ? "green" : quote.status === "stale" ? "amber" : "red";
  return (
    <li className="card price-card" data-status={quote.status}>
      <ProductIcon skuId={quote.sku_id} size={64} />
      <div>
        <h3>{productName(quote.sku_id)}</h3>
        <TrafficLight light={light} />
        {quote.status === "unavailable" || quote.modal_inr == null ? (
          <p className="price-unavailable">{t("price.unavailable")}</p>
        ) : (
          <>
            {quote.status === "stale" && (
              <p className="small">
                <Icon name="clock" size={18} /> {t("price.stale")}
              </p>
            )}
            <p className="price">
              <Icon name="coin" size={24} /> {t("price.modal", { n: quote.modal_inr })}
            </p>
            {quote.min_inr != null && quote.max_inr != null && (
              <p className="small">{t("price.band", { min: quote.min_inr, max: quote.max_inr })}</p>
            )}
          </>
        )}
        <p className="small">{t("price.on", { market: quote.market, date: quote.on })}</p>
        <p className="small source">{t("price.source", { source: quote.source })}</p>
      </div>
    </li>
  );
}

/** The DC lead notes what was really bought, split by where it came from. A record only. */
function Purchases({ skus, markets }: { skus: string[]; markets: string[] }) {
  const [openSku, setOpenSku] = useState<string | null>(null);
  const [saved, setSaved] = useState<string[]>([]);
  if (!skus.length) return null;
  return (
    <>
      <h2>
        <Icon name="tick" /> {t("dc.bought")}
      </h2>
      <p className="small">{t("dc.boughtNote")}</p>
      {openSku ? (
        <PurchaseCard
          key={openSku}
          sku={openSku}
          markets={markets}
          onBack={() => setOpenSku(null)}
          onSaved={() => {
            setSaved((s) => [...s, openSku]);
            setOpenSku(null);
          }}
        />
      ) : (
        <ul className="tiles">
          {skus.map((sku) => (
            <li key={sku}>
              <button className="btn tile" style={{ width: "100%" }} onClick={() => setOpenSku(sku)}>
                <ProductIcon skuId={sku} size={56} />
                <span className="tile-name">{productName(sku)}</span>
                {saved.includes(sku) && (
                  <span className="tile-amount">
                    <Icon name="tick" size={18} /> {t("dc.saved")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function PurchaseCard({ sku, markets, onBack, onSaved }: { sku: string; markets: string[]; onBack: () => void; onSaved: () => void }) {
  const [fpo, setFpo] = useState(0);
  const [spot, setSpot] = useState<Record<string, number>>({});
  const [failed, setFailed] = useState(false);
  const unit = unitOf(sku);
  async function save() {
    setFailed(false);
    try {
      const base = { kind: "purchase", on: todayIso(), sku_id: sku } as const;
      await api.recordOutcome({ ...base, units_bought: fpo, source: "farmer_group" });
      for (const market of markets) {
        await api.recordOutcome({ ...base, units_bought: spot[market] ?? 0, source: "spot", market });
      }
      onSaved();
    } catch {
      setFailed(true);
    }
  }
  return (
    <article className="card order-card">
      <button className="btn btn-plain" onClick={onBack}>
        <Icon name="back" size={28} /> {t("order.back")}
      </button>
      <ProductIcon skuId={sku} size={96} />
      <h2>{productName(sku)}</h2>
      <Counter label={t("dc.fpo")} value={fpo} step={ENTRY_STEP_UNITS} unit={unit} onChange={setFpo} />
      {markets.map((market) => (
        <Counter
          key={market}
          label={t("dc.spotAt", { market })}
          value={spot[market] ?? 0}
          step={ENTRY_STEP_UNITS}
          unit={unit}
          onChange={(n) => setSpot((s) => ({ ...s, [market]: n }))}
        />
      ))}
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <button className="btn btn-yes" style={{ width: "100%" }} onClick={() => void save()}>
        <Icon name="tick" size={40} /> {t("closing.save")}
      </button>
    </article>
  );
}

/** Where one product goes: each area's total, and under it each store's amount. Information only. */
function SendTo({ product }: { product: DcOrders["products"][number] }) {
  const unit = unitOf(product.sku_id);
  const groups = new Map<string, { name: string; rows: typeof product.stores }>();
  for (const row of product.stores) {
    const key = row.area_id ?? "";
    const group = groups.get(key) ?? { name: row.area_name ?? "", rows: [] };
    group.rows.push(row);
    groups.set(key, group);
  }
  return (
    <details className="send-to">
      <summary>{t("dc.sendTo")}</summary>
      {[...groups.entries()].map(([key, group]) => {
        const sum = group.rows.reduce((n, r) => n + r.confirmed_units, 0);
        const waiting = group.rows.reduce((n, r) => n + r.waiting_units, 0);
        return (
          <div key={key} className="send-area">
            <p className="send-head">
              <strong>{group.name}</strong>{" "}
              <strong>{t("dc.sendRow", { n: Math.round(sum), unit })}</strong>
              {waiting > 0 && <span className="small"> · {t("dc.sendWaiting", { n: Math.round(waiting), unit })}</span>}
            </p>
            <ul className="plain-list">
              {group.rows.map((r) => (
                <li key={r.store_id} className="decided-row">
                  <span>{storeLabel(r.store_id)}</span>
                  <span>
                    {r.rejected && r.confirmed_units === 0 && r.waiting_units === 0
                      ? t("dc.sendRejected")
                      : t("dc.sendRow", { n: Math.round(r.confirmed_units || r.waiting_units), unit })}
                    {r.confirmed_units === 0 && r.waiting_units > 0 && <TrafficLight light="amber" />}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </details>
  );
}

/** What the stores have ordered so far, added up per product, and what has been bought. */
function OrdersSoFar({ orders }: { orders: DcOrders }) {
  if (!orders.products.length) return <p className="notice" role="status">{t("dc.orderedNone")}</p>;
  const totalStores = (p: DcOrders["products"][number]) => p.stores_decided + p.stores_waiting + p.stores_rejected;
  const where = (market: string | null) => market ?? t("dc.fromFpo");
  return (
    <>
      <p className={`notice ${orders.all_decided ? "notice-ok" : ""}`} role="status">
        <Icon name={orders.all_decided ? "tick" : "clock"} size={28} /> {orders.all_decided ? t("dc.orderedAll") : t("dc.orderedSome")}
      </p>
      <ul className="tiles-2 dc-grid">
        {[...orders.products]
          .sort((a, b) => b.confirmed_units + b.waiting_units - (a.confirmed_units + a.waiting_units))
          .map((p) => (
            <li key={p.sku_id} className="card total-card">
              <ProductIcon skuId={p.sku_id} size={64} />
              <div className="grow">
                <h3>{productName(p.sku_id)}</h3>
                <p>
                  <strong className="big-number">{Math.round(p.confirmed_units)}</strong> {unitOf(p.sku_id)}
                </p>
                <p className="small">
                  <TrafficLight light={p.stores_waiting === 0 ? "green" : "amber"} />{" "}
                  {t("dc.orderedStores", { done: p.stores_decided + p.stores_rejected, total: totalStores(p) })}
                </p>
                {p.waiting_units > 0 && (
                  <p className="small">{t("dc.orderedWaiting", { n: Math.round(p.waiting_units), unit: unitOf(p.sku_id) })}</p>
                )}
                <SendTo product={p} />
              </div>
            </li>
          ))}
      </ul>
      {orders.bought.length > 0 && (
        <>
          <h3>{t("dc.boughtSoFar")}</h3>
          <ul className="plain-list">
            {orders.bought.map((b) => (
              <li key={`${b.sku_id}-${b.source}-${b.market ?? ""}`} className="decided-row">
                <strong>{productName(b.sku_id)}</strong>
                <span>{t("dc.boughtRow", { units: Math.round(b.units), unit: unitOf(b.sku_id), where: where(b.market) })}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

export function DcScreen() {
  const orders = useLoad(() => api.dcOrders(), []);
  const totals = useLoad(() => api.dcTotals(), []);
  const prices = useLoad(() => api.prices(), []);
  return (
    <div className="stack">
      <h2>
        <Icon name="tick" /> {t("dc.ordered")}
      </h2>
      <p className="small">{t("dc.orderedNote")}</p>
      {orders.state.status === "loading" && <Loading />}
      {orders.state.status === "error" && <LoadError onRetry={orders.reload} />}
      {orders.state.status === "ready" && <OrdersSoFar orders={orders.state.data} />}

      <h2>
        <Icon name="box" /> {t("dc.totals")}
      </h2>
      {totals.state.status === "ready" && (
        <p className="small">
          <Icon name="calendar" size={18} /> {t("dc.forDay", { date: totals.state.data.on })} · {t("dc.totalsNote")}
        </p>
      )}
      {totals.state.status === "ready" && totals.state.data.stale && (
        <p className="notice notice-error" role="status">
          <Icon name="clock" /> {t("app.stale")}
        </p>
      )}
      {totals.state.status === "loading" && <Loading />}
      {totals.state.status === "error" && <LoadError onRetry={totals.reload} />}
      {totals.state.status === "ready" &&
        (() => {
          const max = Math.max(1, ...totals.state.data.totals.map((r) => r.demand.high));
          return (
            <ul className="tiles-2 dc-grid">
              {[...totals.state.data.totals].sort((a, b) => b.demand.likely - a.demand.likely).map((row) => (
                <li key={row.sku_id} className="card total-card">
                  <ProductIcon skuId={row.sku_id} size={64} />
                  <div className="grow">
                    <h3>{productName(row.sku_id)}</h3>
                    <RangeBar range={row.demand} max={max} unit={unitOf(row.sku_id)} />
                  </div>
                </li>
              ))}
            </ul>
          );
        })()}

      {totals.state.status === "ready" && <Purchases
          skus={totals.state.data.totals.map((r) => r.sku_id)}
          markets={orders.state.status === "ready" ? orders.state.data.markets : []}
        />}

      <h2>
        <Icon name="coin" /> {t("dc.prices")}
      </h2>
      {prices.state.status === "loading" && <Loading />}
      {prices.state.status === "error" && <LoadError onRetry={prices.reload} />}
      {prices.state.status === "ready" && !prices.state.data.length && (
        <p className="notice" role="status">
          <Icon name="alert" /> {t("dc.noPrices")}
        </p>
      )}
      {prices.state.status === "ready" && (
        <ul className="tiles-2 dc-grid">
          {prices.state.data.map((q) => (
            <PriceCard key={`${q.sku_id}-${q.market}`} quote={q} />
          ))}
        </ul>
      )}

      <h2>
        <Icon name="tractor" /> {t("dc.trim")}
      </h2>
      <p className="small">{t("dc.trimNote")}</p>
      {totals.state.status === "ready" &&
        (totals.state.data.trimming.length ? (
          <ul className="tiles-2 dc-grid">
            {totals.state.data.trimming.map((tr) => (
              <li key={tr.sku_id} className="card total-card">
                <ProductIcon skuId={tr.sku_id} size={64} />
                <div>
                  <h3>{productName(tr.sku_id)}</h3>
                  <p>
                    <Icon name="minus" size={22} /> {t("dc.trimUnits", { n: Math.round(tr.spot_units_to_trim), unit: unitOf(tr.sku_id) })}
                  </p>
                  <p className="small">{tr.reason}</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <Empty />
        ))}
    </div>
  );
}
