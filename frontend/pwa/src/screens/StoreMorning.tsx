import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Role, Suggestion, TransferPayload } from "../api/types";
import { TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError, TrafficLight, type Light } from "../components/Status";
import { productName, t } from "../i18n/strings";
import { decideAll } from "./decide";
import { biggestGroupFirst, groupSteps, type Group } from "./priority";

/** Transfers and starts on the last day are urgent (red); an early markdown is a check (amber). */
export function lightFor(s: Suggestion): Light {
  if (s.payload.kind === "markdown" && s.payload.earlier_than_last_day) return "amber";
  return "red";
}

export function AlertCard({ group, role, onDone }: { group: Group; role: Role; onDone: () => void }) {
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const first = group.items[0] as Suggestion;
  async function decide(action: "approve" | "reject") {
    if (busy) return;
    setFailed(false);
    setBusy(true);
    const result = await decideAll(role, group.items.map((s) => s.id), { action });
    if (result === "done") onDone();
    else {
      setFailed(true);
      setBusy(false);
    }
  }
  return (
    <li className="card alert-card">
      <TrafficLight light={lightFor(first)} />
      <div className="alert-body">
        <ProductIcon skuId={first.sku_id} size={72} />
        <div>
          <h3>{productName(first.sku_id)}</h3>
          {first.payload.kind === "markdown" && (
            <p>
              <Icon name="tag" size={22} /> <strong>{t("alert.markdown")}</strong>
            </p>
          )}
          {group.items.map((s) => {
            const p = s.payload as MarkdownPayload | TransferPayload;
            return !("to_store" in p) ? (
              <p key={s.id} className="step">
                {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
              </p>
            ) : (
              <p key={s.id}>
                <Icon name="van" size={22} /> {t("alert.transfer")} ·{" "}
                {t("alert.transferDetail", { units: p.units, store: p.to_store, time: p.leave_by })}
              </p>
            );
          })}
          {first.payload.kind === "markdown" && first.payload.earlier_than_last_day && (
            <p className="small">
              <Icon name="clock" size={18} /> {t("alert.earlier")}
            </p>
          )}
          <p className="small">{first.reason}</p>
        </div>
      </div>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} disabled={busy} />
    </li>
  );
}

export function StoreMorning({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () => api.suggestions({ role: "store_manager", store_id: storeId, state: "proposed" }),
    [storeId],
  );
  useChatFocus(state.status === "ready" ? (alerts(state.data)[0]?.items[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const list = alerts(state.data);
  if (!list.length) return <Empty />;
  return (
    <ul className="tiles-2">
      {list.map((g) => (
        <AlertCard key={g.key} group={g} role="store_manager" onDone={reload} />
      ))}
    </ul>
  );
}

/** Red first, then the biggest at stake: most urgent at the top. A product's markdown steps are one card. */
function alerts(all: Suggestion[]): Group[] {
  const rank: Record<Light, number> = { red: 0, amber: 1, green: 2 };
  const shown = all.filter((s) => s.payload.kind === "markdown" || s.payload.kind === "transfer");
  return groupSteps(shown).sort(
    (a, b) => rank[lightFor(a.items[0] as Suggestion)] - rank[lightFor(b.items[0] as Suggestion)] || biggestGroupFirst(a, b),
  );
}
