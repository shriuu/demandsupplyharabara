import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Scorecard, Suggestion, TransferPayload } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Gauge } from "../components/Gauge";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError, TrafficLight } from "../components/Status";
import { productName, storeLabel, t, unitOf } from "../i18n/strings";
import { biggestFirst } from "./priority";

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
  onPick,
}: {
  stores: Scorecard[];
  chain: Scorecard | undefined;
  scope: string;
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
          <span>{t("area.chain")}</span>
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

function ApprovalCard({ s, onDone }: { s: Suggestion; onDone: () => void }) {
  const [failed, setFailed] = useState(false);
  const p = s.payload as MarkdownPayload | TransferPayload;
  async function decide(action: "approve" | "reject") {
    setFailed(false);
    try {
      await api.decide("area_manager", s.id, { action });
      onDone();
    } catch {
      setFailed(true);
    }
  }
  return (
    <li className="card alert-card">
      <div className="alert-body">
        <ProductIcon skuId={s.sku_id} size={72} />
        <div>
          <h3>
            {productName(s.sku_id)} · {storeLabel(s.store_id)}
          </h3>
          {!("to_store" in p) ? (
            <p>
              <Icon name="tag" size={22} /> {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
            </p>
          ) : (
            <p>
              <Icon name="van" size={22} /> {t("alert.transferDetail", { units: `${Math.round(p.units)} ${unitOf(s.sku_id)}`, store: storeLabel(p.to_store), time: p.leave_by })}
            </p>
          )}
          <p className="small">{s.reason}</p>
        </div>
      </div>
      {failed && <p className="notice notice-error" role="alert">{t("app.error")}</p>}
      <TickCross onTick={() => void decide("approve")} onCross={() => void decide("reject")} />
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
  const sorted = [...mine].sort(biggestFirst);
  const shown = all ? sorted : sorted.slice(0, SHORT_LIST);
  return (
    <>
      <ul className="tiles-2">
        {shown.map((s) => (
          <ApprovalCard key={s.id} s={s} onDone={reload} />
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
  const cards = scores.state.status === "ready" ? scores.state.data : [];
  const chain = cards.find((c) => c.scope === "chain") ?? (cards.length === 1 ? cards[0] : undefined);
  const stores = cards.filter((c) => c !== chain).sort(byWorse(chain));
  const shown = scope === "chain" ? chain : stores.find((c) => c.scope === scope);
  return (
    <div className="stack">
      {stores.length > 0 && <StoreNav stores={stores} chain={chain} scope={scope} onPick={setScope} />}
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
      <KillSwitch killed={killed} onChange={onKilledChange} />
    </div>
  );
}
