import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { DcOrders, DcTotals, PriceQuote } from "../api/types";
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
      <summary className="btn btn-plain send-btn">
        <Icon name="van" size={24} /> {t("dc.sendTo")}
      </summary>
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

/** Everything about one product in one row: ordered, tomorrow's total, price, spot advice, what was bought. */
function ProductRow({
  sku,
  order,
  total,
  trim,
  bought,
  saved,
  max,
  onRecord,
}: {
  sku: string;
  order: DcOrders["products"][number] | undefined;
  total: DcTotals["totals"][number] | undefined;
  trim: DcTotals["trimming"][number] | undefined;
  bought: DcOrders["bought"];
  saved: boolean;
  max: number;
  onRecord: () => void;
}) {
  const unit = unitOf(sku);
  const stores = order ? order.stores_decided + order.stores_waiting + order.stores_rejected : 0;
  const where = (market: string | null) => market ?? t("dc.fromFpo");
  return (
    <li className="card dc-row" data-sku={sku}>
      <div className="dc-product">
        <ProductIcon skuId={sku} size={48} />
        <h3>{productName(sku)}</h3>
        {order && <TrafficLight light={order.stores_waiting === 0 ? "green" : "amber"} />}
      </div>
      <div className="dc-block">
        <p className="dc-label">{t("dc.blockOrdered")}</p>
        {order ? (
          <>
            <p>
              <strong className="big-number">{Math.round(order.confirmed_units)}</strong> {unit}
            </p>
            <p className="small">{t("dc.orderedStores", { done: order.stores_decided + order.stores_rejected, total: stores })}</p>
            {order.waiting_units > 0 && <p className="small">{t("dc.orderedWaiting", { n: Math.round(order.waiting_units), unit })}</p>}
          </>
        ) : (
          <p className="small">{t("dc.noOrder")}</p>
        )}
      </div>
      <div className="dc-block">
        <p className="dc-label">{t("dc.blockForecast")}</p>
        {total ? <RangeBar range={total.demand} max={max} unit={unit} /> : <p className="small">{t("dc.noOrder")}</p>}
      </div>
      <div className="dc-block">
        <p className="dc-label">{t("dc.blockTrim")}</p>
        {trim ? (
          <>
            <p>
              <Icon name="minus" size={20} /> {t("dc.trimUnits", { n: Math.round(trim.spot_units_to_trim), unit })}
            </p>
            <details className="dc-why">
              <summary>{t("dc.why")}</summary>
              <p className="small">{trim.reason}</p>
            </details>
          </>
        ) : (
          <p className="small">{t("dc.noTrim")}</p>
        )}
      </div>
      <div className="dc-block">
        <p className="dc-label">{t("dc.blockBought")}</p>
        {bought.map((b) => (
          <p key={`${b.source}-${b.market ?? ""}`} className="small">
            {t("dc.boughtRow", { units: Math.round(b.units), unit, where: where(b.market) })}
          </p>
        ))}
        <button className={`btn ${saved ? "btn-plain" : "btn-yes"}`} onClick={onRecord}>
          <Icon name={saved ? "tick" : "plus"} size={22} /> {saved ? t("dc.saved") : t("dc.record")}
        </button>
      </div>
      {order && order.stores.length > 0 && (
        <div className="dc-send">
          <SendTo product={order} />
        </div>
      )}
    </li>
  );
}

/** The DC buying lead's own measure: how much of what was bought came from farmer groups. */
function FarmerShareCard() {
  const { state } = useLoad(() => api.farmerShare(), []);
  if (state.status !== "ready") return null;
  const share = state.data.share === null ? null : state.data.share * 100;
  return (
    <section className="card" aria-label={t("dc.farmerShare")} data-testid="farmer-share">
      <div className="measure-head">
        <Icon name="tractor" size={26} />
        <span className="measure-name">{t("dc.farmerShare")}</span>
        <strong className="measure-value">{share === null ? "–" : `${Math.round(share * 10) / 10}%`}</strong>
      </div>
      <div className="measure-track" role="img" aria-label={`${t("dc.farmerShare")} ${share === null ? t("score.unknown") : `${Math.round(share)}%`}`}>
        {share !== null && <div className="measure-fill" style={{ width: `${share}%` }} />}
      </div>
      <p className="small">{state.data.definition}</p>
    </section>
  );
}

export function DcScreen() {
  const orders = useLoad(() => api.dcOrders(), []);
  const totals = useLoad(() => api.dcTotals(), []);
  const [openSku, setOpenSku] = useState<string | null>(null);
  const [saved, setSaved] = useState<string[]>([]);

  if (orders.state.status === "loading" || totals.state.status === "loading") return <Loading />;
  if (orders.state.status === "error") return <LoadError onRetry={orders.reload} />;
  if (totals.state.status === "error") return <LoadError onRetry={totals.reload} />;
  const o = orders.state.data;
  const tt = totals.state.data;
  if (openSku) {
    return (
      <PurchaseCard
        key={openSku}
        sku={openSku}
        markets={o.markets}
        onBack={() => setOpenSku(null)}
        onSaved={() => {
          setSaved((x) => [...x, openSku]);
          setOpenSku(null);
        }}
      />
    );
  }
  const skus = [...new Set([...o.products.map((p) => p.sku_id), ...tt.totals.map((r) => r.sku_id)])];
  const ordered = (sku: string) => {
    const p = o.products.find((x) => x.sku_id === sku);
    return p ? p.confirmed_units + p.waiting_units : 0;
  };
  skus.sort((a, b) => ordered(b) - ordered(a));
  const max = Math.max(1, ...tt.totals.map((r) => r.demand.high));
  return (
    <div className="stack">
      <FarmerShareCard />
      <h2>
        <Icon name="box" /> {t("dc.products")}
      </h2>
      <p className="small">
        {t("dc.orderedNote")} <Icon name="calendar" size={16} /> {t("dc.forDay", { date: tt.on })} · {t("dc.totalsNote")}
      </p>
      {o.products.length > 0 && (
        <p className={`notice ${o.all_decided ? "notice-ok" : ""}`} role="status">
          <Icon name={o.all_decided ? "tick" : "clock"} size={28} /> {o.all_decided ? t("dc.orderedAll") : t("dc.orderedSome")}
        </p>
      )}
      {tt.stale && (
        <p className="notice notice-error" role="status">
          <Icon name="clock" /> {t("app.stale")}
        </p>
      )}
      {skus.length === 0 ? (
        <Empty />
      ) : (
        <ul className="dc-rows">
          {skus.map((sku) => (
            <ProductRow
              key={sku}
              sku={sku}
              order={o.products.find((p) => p.sku_id === sku)}
              total={tt.totals.find((r) => r.sku_id === sku)}
              trim={tt.trimming.find((x) => x.sku_id === sku)}
              bought={o.bought.filter((b) => b.sku_id === sku)}
              saved={saved.includes(sku)}
              max={max}
              onRecord={() => setOpenSku(sku)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
