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
import { biggestFirst } from "./priority";

/** Transfers and starts on the last day are urgent (red); an early markdown is a check (amber). */
export function lightFor(s: Suggestion): Light {
  if (s.payload.kind === "markdown" && s.payload.earlier_than_last_day) return "amber";
  return "red";
}

export function AlertCard({
  suggestion,
  role,
  onDone,
}: {
  suggestion: Suggestion;
  role: Role;
  onDone: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const p = suggestion.payload as MarkdownPayload | TransferPayload;
  async function decide(action: "approve" | "reject") {
    setFailed(false);
    try {
      await api.decide(role, suggestion.id, { action });
      onDone();
    } catch {
      setFailed(true);
    }
  }
  return (
    <li className="card alert-card">
      <TrafficLight light={lightFor(suggestion)} />
      <div className="alert-body">
        <ProductIcon skuId={suggestion.sku_id} size={72} />
        <div>
          <h3>{productName(suggestion.sku_id)}</h3>
          {!("to_store" in p) ? (
            <p>
              <Icon name="tag" size={22} /> {t("alert.markdown")} · {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
            </p>
          ) : (
            <p>
              <Icon name="van" size={22} /> {t("alert.transfer")} ·{" "}
              {t("alert.transferDetail", { units: p.units, store: p.to_store, time: p.leave_by })}
            </p>
          )}
          {!("to_store" in p) && p.earlier_than_last_day && (
            <p className="small">
              <Icon name="clock" size={18} /> {t("alert.earlier")}
            </p>
          )}
          <p className="small">{suggestion.reason}</p>
        </div>
      </div>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} />
    </li>
  );
}

export function StoreMorning({ storeId }: { storeId: string }) {
  const { state, reload } = useLoad(
    () => api.suggestions({ role: "store_manager", store_id: storeId, state: "proposed" }),
    [storeId],
  );
  useChatFocus(state.status === "ready" ? (alerts(state.data)[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const list = alerts(state.data);
  if (!list.length) return <Empty />;
  return (
    <ul className="tiles-2">
      {list.map((s) => (
        <AlertCard key={s.id} suggestion={s} role="store_manager" onDone={reload} />
      ))}
    </ul>
  );
}

/** Red first, then the biggest at stake: most urgent at the top. */
function alerts(all: Suggestion[]): Suggestion[] {
  const rank: Record<Light, number> = { red: 0, amber: 1, green: 2 };
  return all
    .filter((s) => s.payload.kind === "markdown" || s.payload.kind === "transfer")
    .sort((a, b) => rank[lightFor(a)] - rank[lightFor(b)] || biggestFirst(a, b));
}
