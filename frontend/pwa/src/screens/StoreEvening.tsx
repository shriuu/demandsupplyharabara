import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { OrderPayload, Suggestion } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { NumberField } from "../components/NumberField";
import { todayIso } from "../components/CalendarPick";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { DriverTag } from "../components/ReasonBadge";
import { Loading, LoadError } from "../components/Status";
import { EDIT_STEP_UNITS, LARGE_EDIT_FRACTION } from "../config";
import { productName, t, unitOf } from "../i18n/strings";
import { decideAll } from "./decide";
import { biggestFirst } from "./priority";

/** The first few tiles are the biggest sellers: shown with an amber edge. */
const TOP_TILES = 3;

export function StoreEvening({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () => api.suggestions({ role: "store_manager", store_id: storeId, kind: "order", recent: true }),
    [storeId],
  );
  const queue = state.status === "ready" ? state.data.filter((s) => s.state === "proposed").sort(biggestFirst) : [];
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!queue.length) {
    // Say what really happened tonight. An older batch is not tonight's: if the last batch was
    // answered, tonight's have simply not arrived yet.
    const latest = state.data.map((s) => s.created_at.slice(0, 10)).sort().pop();
    const lastRun = state.data.filter((s) => s.created_at.slice(0, 10) === latest);
    const answered = lastRun.filter((s) => ["approved", "edited", "rejected", "done"].includes(s.state)).length;
    const late = lastRun.filter((s) => s.state === "expired").length;
    const tonight = latest === todayIso();
    const message = tonight
      ? answered > 0
        ? "order.allDone"
        : late > 0
          ? "order.expiredTonight"
          : "order.notYet"
      : answered === 0 && late > 0
        ? "order.expiredAll"
        : "order.notYet";
    const good = tonight && answered > 0;
    return (
      <>
        <p className={`notice ${good ? "notice-ok" : ""}`} role="status">
          <Icon name={good ? "tick" : "clock"} size={good ? 48 : 32} /> {t(message)}
        </p>
        {tonight && answered > 0 && late > 0 && <p className="small">{t("order.someExpired", { n: late })}</p>}
        {!tonight && answered > 0 && <p className="small">{t("order.lastNight", { ok: answered, late })}</p>}
      </>
    );
  }
  return (
    <>
      <p className="small">
        {t("order.tap")} · {t("order.left", { n: queue.length })}
      </p>
      <p className="small order-legend">
        <span className="chip">
          <Icon name="calendar" size={18} /> 123
        </span>{" "}
        {t("order.legend")}
      </p>
      <ul className="alert-rows order-list">
        {queue.map((s, i) => (
          <OrderRow key={s.id} suggestion={s} rank={i + 1} top={i < TOP_TILES} onDone={reload} />
        ))}
      </ul>
    </>
  );
}

/**
 * One order on one row: the amount with its own minus and plus, a tick and a cross. No page of its own.
 * Changing the amount opens the reason box on this row, and the tick waits for it (every edit has a
 * reason). A cross, and a big change, still ask "are you sure".
 */
function OrderRow({ suggestion, rank, top, onDone }: { suggestion: Suggestion; rank: number; top: boolean; onDone: () => void }) {
  const payload = suggestion.payload as OrderPayload;
  const suggested = Math.round(payload.recommended_units);
  const [units, setUnits] = useState(suggested);
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState<"reject" | "bigEdit" | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const unit = unitOf(suggestion.sku_id);
  const edited = units !== suggested;
  const big = Math.abs(units - suggested) > suggested * LARGE_EDIT_FRACTION;
  const needsReason = edited && reason.trim() === "";
  // the low end of the band is an ordinary day's order; the suggestion also covers a busy day
  const normal = Math.round(payload.range.low);

  async function send(body: Parameters<typeof decideAll>[2]) {
    if (busy) return;
    setConfirming(null);
    setFailed(false);
    setBusy(true);
    const result = await decideAll("store_manager", [suggestion.id], body);
    if (result === "done") onDone();
    else {
      setFailed(true);
      setBusy(false);
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
    <li className={`order-line ${top ? "tile-top" : ""}`} data-testid="order-row" data-sku={suggestion.sku_id}>
      <div className="order-head">
        <span className="tile-rank">{rank}</span>
        <ProductIcon skuId={suggestion.sku_id} size={48} />
        <div className="order-name">
          <span className="row-name">{productName(suggestion.sku_id)}</span>
          <DriverTag driver={suggestion.drivers[0]} reason={suggestion.reason} />
        </div>
        {normal < suggested && (
          <span className="order-band chip" role="img" aria-label={t("order.band", { n: normal })} title={t("order.band", { n: normal })}>
            <Icon name="calendar" size={18} /> {normal}
          </span>
        )}
      </div>
      <div className="order-controls">
        <button className="btn btn-step" aria-label={t("action.minus")} disabled={units <= 0 || busy} onClick={() => setUnits((n) => Math.max(0, n - EDIT_STEP_UNITS))}>
          <Icon name="minus" size={32} />
        </button>
        <NumberField label={t("order.amount")} value={units} onChange={setUnits} unit={unit} />
        <button className="btn btn-step" aria-label={t("action.plus")} disabled={busy} onClick={() => setUnits((n) => n + EDIT_STEP_UNITS)}>
          <Icon name="plus" size={32} />
        </button>
        <TickCross
          onTick={onTick}
          onCross={() => setConfirming("reject")}
          tickLabel={edited ? t("action.save") : t("action.accept")}
          disabled={busy || (edited && needsReason)}
        />
      </div>
      {edited && (
        <label className="reason-field">
          <span>
            <Icon name="mic-off" size={20} /> {t("edit.reason")}
          </span>
          <input className="field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("edit.reasonNeeded")} />
        </label>
      )}
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      {confirming === "reject" && (
        <Confirm message={t("action.confirm.sure")} onYes={() => void send({ action: "reject" })} onNo={() => setConfirming(null)} />
      )}
      {confirming === "bigEdit" && (
        <Confirm message={`${t("edit.large")} ${t("action.confirm.sure")}`} onYes={() => void saveEdit()} onNo={() => setConfirming(null)} />
      )}
    </li>
  );
}
