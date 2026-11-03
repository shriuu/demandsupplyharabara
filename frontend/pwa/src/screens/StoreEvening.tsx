import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { OrderPayload, Suggestion } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { Crates } from "../components/Crates";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { ReasonBadge } from "../components/ReasonBadge";
import { Loading, LoadError } from "../components/Status";
import { EDIT_STEP_UNITS, LARGE_EDIT_FRACTION } from "../config";
import { productName, t } from "../i18n/strings";

export function StoreEvening({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () => api.suggestions({ role: "store_manager", store_id: storeId, kind: "order", state: "proposed" }),
    [storeId],
  );
  const [answered, setAnswered] = useState(0);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const queue = state.data;
  const current = queue[0];
  if (!current) {
    return (
      <p className="notice notice-ok" role="status">
        <Icon name="tick" size={48} /> {t("order.allDone")}
      </p>
    );
  }
  return (
    <OrderCard
      key={current.id}
      suggestion={current}
      position={answered + 1}
      total={answered + queue.length}
      onDone={() => {
        setAnswered((n) => n + 1);
        reload();
      }}
    />
  );
}

export function OrderCard({
  suggestion,
  position,
  total,
  onDone,
}: {
  suggestion: Suggestion;
  position: number;
  total: number;
  onDone: () => void;
}) {
  const payload = suggestion.payload as OrderPayload;
  const [units, setUnits] = useState(payload.recommended_units);
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState<"reject" | "bigEdit" | null>(null);
  const [failed, setFailed] = useState(false);
  const edited = units !== payload.recommended_units;
  const big = Math.abs(units - payload.recommended_units) > payload.recommended_units * LARGE_EDIT_FRACTION;
  const needsReason = edited && reason.trim() === "";
  useChatFocus(suggestion.id);

  async function send(body: Parameters<typeof api.decide>[2]) {
    setConfirming(null);
    setFailed(false);
    try {
      await api.decide("store_manager", suggestion.id, body);
      onDone();
    } catch {
      setFailed(true);
    }
  }
  const saveEdit = () => send({ action: "edit", edited_units: units, reason: reason.trim() });
  const onTick = () => {
    if (!edited) return void send({ action: "approve" });
    if (needsReason) return;
    if (big) return setConfirming("bigEdit");
    void saveEdit();
  };

  return (
    <article className="card order-card">
      <p className="progress" aria-label={t("order.progress", { n: position, total })}>
        {t("order.progress", { n: position, total })}
      </p>
      <div className="product">
        <ProductIcon skuId={suggestion.sku_id} size={112} />
        <h2>{productName(suggestion.sku_id)}</h2>
      </div>
      <Crates units={units} range={payload.range} />
      <div className="stepper">
        <button
          className="btn btn-step"
          aria-label={t("action.minus")}
          disabled={units <= 0}
          onClick={() => setUnits((n) => Math.max(0, n - EDIT_STEP_UNITS))}
        >
          <Icon name="minus" size={40} />
        </button>
        <button className="btn btn-step" aria-label={t("action.plus")} onClick={() => setUnits((n) => n + EDIT_STEP_UNITS)}>
          <Icon name="plus" size={40} />
        </button>
      </div>
      {payload.manager_rule_units != null && (
        <p className="usual">{t("order.usual", { n: payload.manager_rule_units })}</p>
      )}
      <ReasonBadge driver={suggestion.drivers[0]} reason={suggestion.reason} />
      {edited && (
        <label className="reason-field">
          <span>
            <Icon name="mic-off" size={20} /> {t("edit.reason")}
          </span>
          <input
            className="field"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("edit.reasonNeeded")}
          />
        </label>
      )}
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross
        onTick={onTick}
        onCross={() => setConfirming("reject")}
        tickLabel={edited ? t("action.save") : t("action.accept")}
        disabled={edited && needsReason}
      />
      {confirming === "reject" && (
        <Confirm message={t("action.confirm.sure")} onYes={() => void send({ action: "reject" })} onNo={() => setConfirming(null)} />
      )}
      {confirming === "bigEdit" && (
        <Confirm message={`${t("edit.large")} ${t("action.confirm.sure")}`} onYes={() => void saveEdit()} onNo={() => setConfirming(null)} />
      )}
    </article>
  );
}
