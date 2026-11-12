import { useState } from "react";
import { api } from "../api/client";
import { loadSession } from "../api/session";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Scorecard, Suggestion, TransferPayload } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Gauge } from "../components/Gauge";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError, TrafficLight } from "../components/Status";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";
import { Trend } from "./Trend";
import { WeekBoard } from "./WeekBoard";
import { decideAll } from "./decide";
import { biggestGroupFirst, groupSteps, type Group } from "./priority";

/** Waste, empty shelves and farmer share: always the same three gauges, side by side (G04). */
export function Scoreboard({ card, title }: { card: Scorecard; title?: string }) {
  return (
    <section className="card scoreboard" aria-label={t("area.scoreboard")} data-scope={card.scope}>
      <h3>{title ?? (card.scope === "chain" ? t("area.chain") : storeLabel(card.scope))}</h3>
      <div className="gauges">
        <Gauge label="score.waste" icon="bag" value={card.waste_pct} goodWhen="low" />
        <Gauge label="score.stockout" icon="box" value={card.stockout_pct} goodWhen="low" />
        <Gauge
          label="score.farmer"
          icon="tractor"
          value={card.farmer_share == null ? null : card.farmer_share * 100}
          goodWhen="high"
        />
      </div>
      {card.farmer_share_definition && <p className="small">{card.farmer_share_definition}</p>}
    </section>
  );
}

/** How many cards to show before the rest: the queue is ordered by value, biggest first. */
const SHORT_LIST = 8;

type Light = "red" | "amber" | "green";

/** Compared with the chain, so no fixed limit is needed here. */
function compare(card: Scorecard, chain: Scorecard | undefined) {
  const wasteWorse =
    !!chain && card.waste_pct != null && chain.waste_pct != null && card.waste_pct > chain.waste_pct;
  const emptyWorse =
    !!chain && card.stockout_pct != null && chain.stockout_pct != null && card.stockout_pct > chain.stockout_pct;
  const light: Light = wasteWorse && emptyWorse ? "red" : wasteWorse || emptyWorse ? "amber" : "green";
  return { wasteWorse, emptyWorse, light };
}

/** Stores worse than the chain come first in the navigation. */
function byWorse(chain: Scorecard | undefined) {
  const rank: Record<Light, number> = { red: 0, amber: 1, green: 2 };
  return (a: Scorecard, b: Scorecard) => rank[compare(a, chain).light] - rank[compare(b, chain).light];
}

function StoreNav({
  stores,
  chain,
  scope,
  allLabel,
  onPick,
}: {
  stores: Scorecard[];
  chain: Scorecard | undefined;
  scope: string;
  allLabel: string;
  onPick: (scope: string) => void;
}) {
  return (
    <nav aria-label={t("area.pick")}>
      <p className="small">{t("area.storesNote")}</p>
      <div className="nav-scroll">
        <button
          className={`btn nav-tile ${scope === "chain" ? "nav-on" : ""}`}
          aria-pressed={scope === "chain"}
          onClick={() => onPick("chain")}
        >
          <Icon name="chart" size={28} />
          <span>{allLabel}</span>
        </button>
        {stores.map((c) => (
          <button
            key={c.scope}
            className={`btn nav-tile ${scope === c.scope ? "nav-on" : ""}`}
            aria-pressed={scope === c.scope}
            onClick={() => onPick(c.scope)}
          >
            <Icon name="store" size={28} />
            <span>{storeLabel(c.scope)}</span>
            <TrafficLight light={compare(c, chain).light} />
          </button>
        ))}
      </div>
    </nav>
  );
}

function StoreNote({ card, chain }: { card: Scorecard; chain: Scorecard | undefined }) {
  if (card === chain) return null;
  const { wasteWorse, emptyWorse } = compare(card, chain);
  return (
    <>
      {wasteWorse && <p className="small">{t("area.worseWaste")}</p>}
      {emptyWorse && <p className="small">{t("area.worseEmpty")}</p>}
      {!wasteWorse && !emptyWorse && <p className="small">{t("area.fine")}</p>}
    </>
  );
}

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

/** What the store managers have already decided, so the area manager sees the other roles' work. */
function StoresDecided({ scope, onPick }: { scope: string; onPick: (scope: string) => void }) {
  const { state } = useLoad(() => api.suggestions({}), []);
  if (state.status !== "ready") return null;
  const mine = state.data.filter((s) => s.approver_role === "store_manager" && (scope === "chain" || s.store_id === scope));
  if (!mine.length) return null;
  type Row = { ok: number; edit: number; no: number; wait: number; kinds: Record<string, number> };
  const rows = new Map<string, Row>();
  for (const s of mine) {
    const row = rows.get(s.store_id) ?? { ok: 0, edit: 0, no: 0, wait: 0, kinds: {} };
    if (s.state === "approved" || s.state === "done") row.ok += 1;
    else if (s.state === "edited") row.edit += 1;
    else if (s.state === "rejected") row.no += 1;
    else if (s.state === "proposed") {
      row.wait += 1;
      row.kinds[s.payload.kind] = (row.kinds[s.payload.kind] ?? 0) + 1;
    }
    rows.set(s.store_id, row);
  }
  const kindLine = (kinds: Record<string, number>) =>
    (["order", "markdown", "transfer", "surplus"] as const)
      .filter((k) => kinds[k])
      .map((k) => `${kinds[k]} ${t(`kind.${k}`)}`)
      .join(" · ");
  return (
    <section className="card" aria-label={t("area.decided")}>
      <h3>{t("area.decided")}</h3>
      <p className="small">{t("area.decidedNote")}</p>
      {[...rows.entries()].map(([store, r]) =>
        scope === "chain" ? (
          <button
            key={store}
            className="btn btn-plain decided-row"
            onClick={() => {
              onPick(store);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <strong>{storeLabel(store)}</strong>
            <span>{t("area.decidedRow", { ok: r.ok, edit: r.edit, no: r.no, wait: r.wait })}</span>
          </button>
        ) : (
          <div key={store}>
            <p className="decided-row">
              <strong>{storeLabel(store)}</strong>
              <span>{t("area.decidedRow", { ok: r.ok, edit: r.edit, no: r.no, wait: r.wait })}</span>
            </p>
            {r.wait > 0 && <p className="small">{t("area.waitingKinds", { list: kindLine(r.kinds) })}</p>}
          </div>
        ),
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

function Queue({ killed, scope }: { killed: boolean; scope: string }) {
  const [all, setAll] = useState(false);
  const { state, reload } = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), String(killed));
  useChatFocus(state.status === "ready" ? (state.data[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const mine = state.data.filter((s) => scope === "chain" || s.store_id === scope);
  if (!mine.length) return <Empty />;
  const sorted = groupSteps(mine).sort(biggestGroupFirst);
  const shown = all ? sorted : sorted.slice(0, SHORT_LIST);
  return (
    <>
      <ul className="tiles-2">
        {shown.map((g) => (
          <ApprovalCard key={g.key} group={g} showStore={scope === "chain"} onDone={reload} />
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
  const scores = useLoad(() => api.scorecard(), []);
  const recorded = useLoad(() => api.recordedScorecard(), []);
  const [scope, setScope] = useState("chain");
  const session = loadSession();
  const limited = !!session?.area_id; // an area manager sees only their own stores
  const allLabel = session?.area_name ?? t("area.chain");
  const cards = scores.state.status === "ready" ? scores.state.data : [];
  const chain = cards.find((c) => c.scope === "chain") ?? (cards.length === 1 ? cards[0] : undefined);
  const stores = cards.filter((c) => c !== chain).sort(byWorse(chain));
  const shown = scope === "chain" ? chain : stores.find((c) => c.scope === scope);
  return (
    <div className="stack">
      {stores.length > 0 && <StoreNav stores={stores} chain={chain} scope={scope} allLabel={allLabel} onPick={setScope} />}
      <h2>
        <Icon name="chart" /> {t("area.scoreboard")}
      </h2>
      {scores.state.status === "loading" && <Loading />}
      {scores.state.status === "error" && <LoadError onRetry={scores.reload} />}
      {scores.state.status === "ready" && !cards.length && <Empty />}
      {shown && (
        <>
          <Scoreboard card={shown} />
          <StoreNote card={shown} chain={chain} />
        </>
      )}
      {!shown && scope === "chain" && stores.length > 0 && <p className="notice" role="status">{t("area.pickStore")}</p>}
      <Trend scope={scope} />
      {scope !== "chain" && <CallStore storeId={scope} />}
      <StoresDecided scope={scope} onPick={setScope} />
      {scope === "chain" && (
        <WeekBoard
          onPick={(store) => {
            setScope(store);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      )}
      {recorded.state.status === "ready" && (
        <>
          <h3>{t("area.recorded")}</h3>
          {(() => {
            const mine = recorded.state.data.find((c) => c.scope === scope);
            return mine ? (
              <>
                <Scoreboard card={mine} title={t("area.recorded")} />
                <p className="small">{t("area.recordedNote")}</p>
              </>
            ) : (
              <p className="notice" role="status">
                {t("area.recordedNone")}
              </p>
            );
          })()}
        </>
      )}
      <h2>
        <Icon name="tick" /> {t("area.todo")}
      </h2>
      <p className="small">{t("area.todoNote")}</p>
      <Queue killed={killed} scope={scope} />
      {!limited && <KillSwitch killed={killed} onChange={onKilledChange} />}
    </div>
  );
}
