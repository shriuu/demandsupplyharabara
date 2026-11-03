import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { Suggestion, SurplusPayload } from "../api/types";
import { TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError } from "../components/Status";
import { productName, t } from "../i18n/strings";

function SurplusCard({ suggestion, onDone }: { suggestion: Suggestion; onDone: () => void }) {
  const p = suggestion.payload as SurplusPayload;
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
          <h3>{productName(suggestion.sku_id)}</h3>
          <p>
            <Icon name="bag" size={22} /> {p.units} · {t("surplus.grade", { grade: p.grade })}
          </p>
          <p>
            <Icon name="clock" size={22} /> {t("surplus.pickup", { window: p.pickup_window })}
          </p>
          <p className="small">
            <Icon name="coin" size={18} /> {t("surplus.recovery", { inr: p.expected_recovery_inr })}
          </p>
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
  if (!state.data.length) return <Empty />;
  return (
    <ul className="stack">
      {state.data.map((s) => (
        <SurplusCard key={s.id} suggestion={s} onDone={reload} />
      ))}
    </ul>
  );
}
