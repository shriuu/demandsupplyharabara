import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { OrderPayload, Suggestion } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { Crates } from "../components/Crates";
import { NumberField } from "../components/NumberField";
import { useChatFocus } from "../components/chatContext";
import { todayIso } from "../components/CalendarPick";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { ReasonBadge } from "../components/ReasonBadge";
import { Loading, LoadError } from "../components/Status";
import { EDIT_STEP_UNITS, LARGE_EDIT_FRACTION } from "../config";
import { productName, t, unitOf } from "../i18n/strings";
import { decideAll } from "./decide";
import { biggestFirst } from "./priority";

/** The first few tiles are the biggest sellers: shown with an amber edge. */
const TOP_TILES = 3;

export function StoreEvening({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () =>
      api.suggestions({
        role: "store_manager",
        store_id: storeId,
        kind: "order",
      }),
    [storeId],
  );
  const [openId, setOpenId] = useState<string | null>(null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const queue = state.data
    .filter((s) => s.state === "proposed")
    .sort(biggestFirst);
  if (!queue.length) {
    // Say what really happened tonight. An older batch is not tonight's: if the last batch was
    // answered, tonight's have simply not arrived yet.
    const latest = state.data
      .map((s) => s.created_at.slice(0, 10))
      .sort()
      .pop();
    const lastRun = state.data.filter(
      (s) => s.created_at.slice(0, 10) === latest,
    );
    const answered = lastRun.filter((s) =>
      ["approved", "edited", "rejected", "done"].includes(s.state),
    ).length;
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
          <Icon name={good ? "tick" : "clock"} size={good ? 48 : 32} />{" "}
          {t(message)}
        </p>
        {tonight && answered > 0 && late > 0 && (
          <p className="small">{t("order.someExpired", { n: late })}</p>
        )}
        {!tonight && answered > 0 && (
          <p className="small">
            {t("order.lastNight", { ok: answered, late })}
          </p>
        )}
      </>
    );
  }
  const open = queue.find((s) => s.id === openId);
  if (open) {
    return (
      <>
        <button className="btn btn-plain" onClick={() => setOpenId(null)}>
          <Icon name="back" size={28} /> {t("order.back")}
        </button>
        <OrderCard
          key={open.id}
          suggestion={open}
          position={queue.indexOf(open) + 1}
          total={queue.length}
          onDone={() => {
            setOpenId(null);
            reload();
          }}
        />
      </>
    );
  }
  return (
    <>
      <p className="small">
        {t("order.tap")} · {t("order.left", { n: queue.length })}
      </p>
      <ul className="tiles">
        {queue.map((s, i) => {
          const units = (s.payload as OrderPayload).recommended_units;
          return (
            <li key={s.id}>
              <button
                className={`btn tile ${i < TOP_TILES ? "tile-top" : ""}`}
                style={{ width: "100%" }}
                onClick={() => setOpenId(s.id)}
              >
                <span className="tile-rank">{i + 1}</span>
                <ProductIcon skuId={s.sku_id} size={72} />
                <span className="tile-name">{productName(s.sku_id)}</span>
                <span className="tile-amount">
                  {t("order.units", {
                    n: Math.round(units),
                    unit: unitOf(s.sku_id),
                  })}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </>
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
  const suggested = Math.round(payload.recommended_units);
  const [units, setUnits] = useState(suggested);
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState<"reject" | "bigEdit" | null>(
    null,
  );
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const edited = units !== suggested;
  const big = Math.abs(units - suggested) > suggested * LARGE_EDIT_FRACTION;
  const needsReason = edited && reason.trim() === "";
  useChatFocus(suggestion.id);

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
  const saveEdit = () =>
    send({ action: "edit", edited_units: units, reason: reason.trim() });
  const onTick = () => {
    if (!edited) return void send({ action: "approve" });
    if (needsReason) return;
    if (big) return setConfirming("bigEdit");
    void saveEdit();
  };

  return (
    <article className="card order-card">
      <p
        className="progress"
        aria-label={t("order.progress", { n: position, total })}
      >
        {t("order.progress", { n: position, total })}
      </p>
      <div className="product">
        <ProductIcon skuId={suggestion.sku_id} size={112} />
        <h2>{productName(suggestion.sku_id)}</h2>
      </div>
      <Crates units={units} range={payload.range} skuId={suggestion.sku_id} />
      <div className="stepper">
        <button
          className="btn btn-step"
          aria-label={t("action.minus")}
          disabled={units <= 0}
          onClick={() => setUnits((n) => Math.max(0, n - EDIT_STEP_UNITS))}
        >
          <Icon name="minus" size={40} />
        </button>
        <NumberField
          label={t("order.amount")}
          value={units}
          onChange={setUnits}
          unit={unitOf(suggestion.sku_id)}
        />
        <button
          className="btn btn-step"
          aria-label={t("action.plus")}
          onClick={() => setUnits((n) => n + EDIT_STEP_UNITS)}
        >
          <Icon name="plus" size={40} />
        </button>
      </div>
      {payload.manager_rule_units != null && (
        <p className="usual">
          {t("order.usual", { n: Math.round(payload.manager_rule_units) })}
        </p>
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
      {failed && (
        <p className="notice notice-error" role="alert">
          {t("app.error")}
        </p>
      )}
      <TickCross
        onTick={onTick}
        onCross={() => setConfirming("reject")}
        tickLabel={edited ? t("action.save") : t("action.accept")}
        disabled={busy || (edited && needsReason)}
      />
      {confirming === "reject" && (
        <Confirm
          message={t("action.confirm.sure")}
          onYes={() => void send({ action: "reject" })}
          onNo={() => setConfirming(null)}
        />
      )}
      {confirming === "bigEdit" && (
        <Confirm
          message={`${t("edit.large")} ${t("action.confirm.sure")}`}
          onYes={() => void saveEdit()}
          onNo={() => setConfirming(null)}
        />
      )}
    </article>
  );
}
