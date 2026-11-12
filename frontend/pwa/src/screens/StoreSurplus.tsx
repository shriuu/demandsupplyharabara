import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { Suggestion, SurplusPayload } from "../api/types";
import { TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Loading, LoadError } from "../components/Status";
import { todayIso } from "../dates";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";

/** "today", "tomorrow", or the weekday and date: a morning window must never look like this morning. */
function pickupDay(iso: string): string {
  const days = Math.round((Date.parse(`${iso}T00:00:00Z`) - Date.parse(`${todayIso()}T00:00:00Z`)) / 86_400_000);
  if (days === 0) return t("surplus.today");
  if (days === 1) return t("surplus.tomorrow");
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

export function SurplusCard({ suggestion, onDone }: { suggestion: Suggestion; onDone: () => void }) {
  const p = suggestion.payload as SurplusPayload;
  const free = p.price_share_of_retail === 0; // a food bank: nothing comes back
  const [failed, setFailed] = useState(false);
  async function decide(action: "approve" | "reject") {
    setFailed(false);
    try {
      await api.decide("store_manager", suggestion.id, { action });
      onDone();
    } catch {
      setFailed(true);
    }
  }
  return (
    <li className="card surplus-card">
      <div className="alert-body">
        <span className="buyer-logo" aria-label={t("surplus.buyer", { id: p.buyer_id })}>
          {p.buyer_id.slice(0, 2)}
        </span>
        <ProductIcon skuId={suggestion.sku_id} size={72} />
        <div>
          <h3>
            {t("surplus.give", { units: Math.round(p.units), unit: unitOf(suggestion.sku_id), product: productName(suggestion.sku_id) })}
          </h3>
          <p>
            <Icon name="bag" size={22} /> {t("surplus.to", { buyer: p.buyer_name ?? p.buyer_id })}
          </p>
          <p>
            <Icon name="home" size={22} /> {t("surplus.from", { store: storeLabel(suggestion.store_id) })}
          </p>
          <p>
            <Icon name="clock" size={22} />{" "}
            {p.pickup_date
              ? t("surplus.pickupDay", { day: pickupDay(p.pickup_date), window: p.pickup_window })
              : t("surplus.pickup", { window: p.pickup_window })}
          </p>
          <p>
            <Icon name="coin" size={22} />{" "}
            {free ? t("surplus.free") : t("surplus.youGet", { inr: Math.round(p.expected_recovery_inr) })}
          </p>
          {p.price_share_of_retail != null && !free && (
            <p className="small">{t("surplus.share", { pct: Math.round(p.price_share_of_retail * 100) })}</p>
          )}
          {p.profit_vs_cost_inr != null && (
            <p className="small">
              {p.profit_vs_cost_inr < 0
                ? t("surplus.vsCostBelow", { n: Math.round(-p.profit_vs_cost_inr) })
                : t("surplus.vsCostAbove", { n: Math.round(p.profit_vs_cost_inr) })}
            </p>
          )}
        </div>
      </div>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} />
    </li>
  );
}

export function StoreSurplus({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () => api.suggestions({ role: "store_manager", store_id: storeId, kind: "surplus", state: "proposed" }),
    [storeId],
  );
  useChatFocus(state.status === "ready" ? (state.data[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <p className="notice" role="status">{t("surplus.none")}</p>;
  return (
    <ul className="stack">
      {state.data.map((s) => (
        <SurplusCard key={s.id} suggestion={s} onDone={reload} />
      ))}
    </ul>
  );
}
