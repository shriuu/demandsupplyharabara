import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { PriceQuote } from "../api/types";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { RangeBar } from "../components/RangeBar";
import { Empty, Loading, LoadError, TrafficLight } from "../components/Status";
import { productName, t, unitOf } from "../i18n/strings";

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

export function DcScreen() {
  const totals = useLoad(() => api.dcTotals(), []);
  const prices = useLoad(() => api.prices(), []);
  return (
    <div className="stack">
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
            <ul className="tiles-2">
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
        <ul className="tiles-2">
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
          <ul className="tiles-2">
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
