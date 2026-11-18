import { useState } from "react";
import { api } from "../api/client";
import { loadSession } from "../api/session";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Suggestion, TransferPayload } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Icon } from "../components/Icons";
import { WhyLine } from "../components/WhyLine";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError } from "../components/Status";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";
import { ProductDashboard } from "./ProductDashboard";
import { StoreCards } from "./StoreCards";
import { StoreHistory } from "./StoreHistory";
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
    <li className="alert-row" data-testid="approval-row">
      <ProductIcon skuId={first.sku_id} size={56} />
      <div className="alert-main">
        <h3>{showStore ? `${productName(first.sku_id)} · ${storeLabel(first.store_id)}` : productName(first.sku_id)}</h3>
        <div className="alert-chips">
          {group.items.map((s) => {
            const p = s.payload as MarkdownPayload | TransferPayload;
            return !("to_store" in p) ? (
              <span key={s.id} className="chip">
                <Icon name="tag" size={18} /> {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
              </span>
            ) : (
              <span key={s.id} className="chip">
                <Icon name="van" size={18} />{" "}
                {t("alert.transferDetail", { units: `${Math.round(p.units)} ${unitOf(s.sku_id)}`, store: storeLabel(p.to_store), time: p.leave_by })}
              </span>
            );
          })}
          <WhyLine suggestion={first} />
        </div>
      </div>
      <div className="alert-actions">
        <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} disabled={busy} />
      </div>
      {failed && <p className="notice notice-error alert-fail" role="alert">{t("app.error")}</p>}
    </li>
  );
}

function Queue({ killed, store }: { killed: boolean; store?: string }) {
  const [all, setAll] = useState(false);
  const { state, reload } = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), String(killed));
  // the question in the Ask panel is about the first card in front of the person, in this store only
  const first = state.status === "ready" ? state.data.find((x) => !store || x.store_id === store) : undefined;
  useChatFocus(first?.id ?? null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  const rows = store ? state.data.filter((s) => s.store_id === store) : state.data;
  if (!rows.length) return store ? <p className="notice">{t("area.noneHere")}</p> : <Empty />;
  const sorted = groupSteps(rows).sort(biggestGroupFirst);
  const shown = all ? sorted : sorted.slice(0, SHORT_LIST);
  return (
    <>
      <ul className="alert-rows order-list">
        {shown.map((g) => (
          <ApprovalCard key={g.key} group={g} showStore={!store} onDone={reload} />
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

function StoreView({ store, killed, onBack }: { store: string; killed: boolean; onBack: () => void }) {
  const [tab, setTab] = useState<"decisions" | "performance" | "orders">("decisions");
  return (
    <div className="stack">
      <button className="btn btn-plain" onClick={onBack}>
        <Icon name="back" size={24} /> {t("area.back")}
      </button>
      <h2>
        <Icon name="store" /> {storeLabel(store)}
      </h2>
      <CallStore storeId={store} />
      <div className="area-tabs" role="group">
        {(["decisions", "performance", "orders"] as const).map((k) => (
          <button
            key={k}
            className={`btn nav-tile ${tab === k ? "nav-on" : ""}`}
            aria-pressed={tab === k}
            onClick={() => setTab(k)}
          >
            <Icon name={k === "decisions" ? "tick" : k === "performance" ? "chart" : "box"} size={24} /> {t(`area.tab.${k}`)}
          </button>
        ))}
      </div>
      {tab === "decisions" && <Queue killed={killed} store={store} />}
      {tab === "performance" && <Trend scope={store} onPick={() => undefined} />}
      {tab === "orders" && (
        <div className="stack">
          <ProductDashboard key={`p-${store}`} period="week" storeId={store} />
          <StoreHistory key={`h-${store}`} storeId={store} />
        </div>
      )}
    </div>
  );
}

export function AreaScreen({ killed, onKilledChange }: { killed: boolean; onKilledChange: (killed: boolean) => void }) {
  const [store, setStore] = useState<string | null>(null);
  const session = loadSession();
  const limited = !!session?.area_id; // an area manager sees only their own stores
  const allLabel = session?.area_name ?? t("area.chain");
  if (store) {
    return <StoreView store={store} killed={killed} onBack={() => setStore(null)} />;
  }
  const pick = (scope: string) => {
    if (scope !== "chain") {
      setStore(scope);
      window.scrollTo({ top: 0 });
    }
  };
  return (
    <div className="stack">
      <h2>
        <Icon name="store" /> {t("area.stores")}
      </h2>
      <StoreCards scope="chain" onPick={pick} allLabel={allLabel} />
      {!limited && <KillSwitch killed={killed} onChange={onKilledChange} />}
    </div>
  );
}
