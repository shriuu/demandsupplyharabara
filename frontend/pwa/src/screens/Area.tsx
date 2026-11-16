import { useState } from "react";
import { api } from "../api/client";
import { loadSession } from "../api/session";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Suggestion, TransferPayload } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError } from "../components/Status";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";
import { StoreCards } from "./StoreCards";
import { Trend } from "./Trend";
import { decideAll } from "./decide";
import { biggestGroupFirst, groupSteps, type Group } from "./priority";

/** How many cards to show before the rest: the queue is ordered by value, biggest first. */
const SHORT_LIST = 8;

/** A tap to call the store's manager. No number in the file means no button: nothing is guessed. */
function CallStore({ storeId }: { storeId: string }) {
  const { state } = useLoad(() => api.contacts(), []);
  if (state.status !== "ready") return null;
  const row = state.data.find((c) => c.store_id === storeId);
  const phone = row?.phone;
  return (
    <section className="card contact" aria-label={t("area.callTitle")}>
      {phone ? (
        <a className="btn btn-yes btn-call" href={`tel:${phone.replace(/[^+\d]/g, "")}`}>
          <Icon name="phone" size={32} /> {t("area.call", { who: row?.name ?? t("area.callWho") })}
          <small>{phone}</small>
        </a>
      ) : (
        <p className="small">{t("area.callNone")}</p>
      )}
    </section>
  );
}

function ApprovalCard({ group, showStore, onDone }: { group: Group; showStore: boolean; onDone: () => void }) {
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const first = group.items[0] as Suggestion;
  async function decide(action: "approve" | "reject") {
    if (busy) return;
    setFailed(false);
    setBusy(true);
    const result = await decideAll("area_manager", group.items.map((s) => s.id), { action });
    if (result === "done") onDone();
    else {
      setFailed(true);
      setBusy(false);
    }
  }
  return (
    <li className="card alert-card">
      <div className="alert-body">
        <ProductIcon skuId={first.sku_id} size={72} />
        <div>
          <h3>{showStore ? `${productName(first.sku_id)} · ${storeLabel(first.store_id)}` : productName(first.sku_id)}</h3>
          {group.items.map((s) => {
            const p = s.payload as MarkdownPayload | TransferPayload;
            return !("to_store" in p) ? (
              <p key={s.id}>
                <Icon name="tag" size={22} /> {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
              </p>
            ) : (
              <p key={s.id}>
                <Icon name="van" size={22} /> {t("alert.transferDetail", { units: `${Math.round(p.units)} ${unitOf(s.sku_id)}`, store: storeLabel(p.to_store), time: p.leave_by })}
              </p>
            );
          })}
          <p className="small">{first.reason}</p>
        </div>
      </div>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} disabled={busy} />
    </li>
  );
}

function Queue({ killed }: { killed: boolean }) {
  const [all, setAll] = useState(false);
  const { state, reload } = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), String(killed));
  useChatFocus(state.status === "ready" ? (state.data[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const sorted = groupSteps(state.data).sort(biggestGroupFirst);
  const shown = all ? sorted : sorted.slice(0, SHORT_LIST);
  return (
    <>
      <ul className="tiles-2">
        {shown.map((g) => (
          <ApprovalCard key={g.key} group={g} showStore onDone={reload} />
        ))}
      </ul>
      {!all && sorted.length > SHORT_LIST && (
        <button className="btn btn-plain" onClick={() => setAll(true)}>
          {t("area.showAll", { n: sorted.length })}
        </button>
      )}
    </>
  );
}

function KillSwitch({ killed, onChange }: { killed: boolean; onChange: (killed: boolean) => void }) {
  const [asking, setAsking] = useState(false);
  const [failed, setFailed] = useState(false);
  async function flip() {
    setAsking(false);
    setFailed(false);
    try {
      const result = await api.setKillSwitch(!killed);
      onChange(result.kill_switch);
    } catch {
      setFailed(true);
    }
  }
  return (
    <section className="kill">
      {killed && (
        <p className="notice notice-error" role="status">
          <Icon name="stop" /> {t("kill.stoppedNow")}
        </p>
      )}
      <button className={`btn ${killed ? "btn-yes" : "btn-danger"}`} onClick={() => setAsking(true)}>
        <Icon name={killed ? "tick" : "stop"} size={36} /> {killed ? t("kill.off") : t("kill.on")}
      </button>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      {asking && (
        <Confirm
          message={killed ? t("kill.confirmOff") : t("kill.confirm")}
          onYes={() => void flip()}
          onNo={() => setAsking(false)}
        />
      )}
    </section>
  );
}

export function AreaScreen({ killed, onKilledChange }: { killed: boolean; onKilledChange: (killed: boolean) => void }) {
  const [scope, setScope] = useState("chain");
  const session = loadSession();
  const limited = !!session?.area_id; // an area manager sees only their own stores
  const allLabel = session?.area_name ?? t("area.chain");
  return (
    <div className="stack">
      <h2>
        <Icon name="tick" /> {t("area.todo")}
      </h2>
      <p className="small">{t("area.todoNote")}</p>
      <Queue killed={killed} />
      <h2>
        <Icon name="store" /> {t("area.stores")}
      </h2>
      <StoreCards scope={scope} onPick={setScope} allLabel={allLabel} />
      <Trend
        scope={scope}
        onPick={(store) => {
          setScope(store);
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />
      {scope !== "chain" && <CallStore storeId={scope} />}
      {!limited && <KillSwitch killed={killed} onChange={onKilledChange} />}
    </div>
  );
}
