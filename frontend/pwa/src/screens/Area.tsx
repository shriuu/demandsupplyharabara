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

/** Waste, empty shelves and farmer share: always the same three gauges, side by side (G04). */
export function Scoreboard({ card }: { card: Scorecard }) {
  return (
    <section className="card scoreboard" aria-label={t("area.scoreboard")} data-scope={card.scope}>
      <h3>{card.scope === "chain" ? t("area.chain") : storeLabel(card.scope)}</h3>
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

function Scores() {
  const { state, reload } = useLoad(() => api.scorecard(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const chain = state.data.find((c) => c.scope === "chain") ?? (state.data.length === 1 ? state.data[0] : undefined);
  const stores = state.data.filter((c) => c !== chain);
  // Compared with the chain, so no fixed limit is needed here.
  const gap = (c: Scorecard) =>
    chain && c.waste_pct != null && chain.waste_pct != null && c.stockout_pct != null && chain.stockout_pct != null
      ? c.waste_pct - chain.waste_pct + (c.stockout_pct - chain.stockout_pct)
      : 0;
  const ordered = [...stores].sort((a, b) => gap(b) - gap(a));
  return (
    <>
      {chain && <Scoreboard card={chain} />}
      <h3>{t("area.stores")}</h3>
      <p className="small">{t("area.storesNote")}</p>
      <ul className="stack">
        {ordered.map((c) => {
          const wasteWorse = !!chain && c.waste_pct != null && chain.waste_pct != null && c.waste_pct > chain.waste_pct;
          const emptyWorse =
            !!chain && c.stockout_pct != null && chain.stockout_pct != null && c.stockout_pct > chain.stockout_pct;
          return (
            <li key={c.scope} className="card" data-scope={c.scope}>
              <h3>{storeLabel(c.scope)}</h3>
              <TrafficLight light={wasteWorse && emptyWorse ? "red" : wasteWorse || emptyWorse ? "amber" : "green"} />
              <p>
                <Icon name="bag" size={22} /> {t("score.waste")}: {c.waste_pct == null ? t("score.unknown") : `${c.waste_pct.toFixed(1)}%`}
                {" · "}
                <Icon name="box" size={22} /> {t("score.stockout")}: {c.stockout_pct == null ? t("score.unknown") : `${c.stockout_pct.toFixed(1)}%`}
              </p>
              {wasteWorse && <p className="small">{t("area.worseWaste")}</p>}
              {emptyWorse && <p className="small">{t("area.worseEmpty")}</p>}
              {!wasteWorse && !emptyWorse && <p className="small">{t("area.fine")}</p>}
            </li>
          );
        })}
      </ul>
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

function Queue({ killed }: { killed: boolean }) {
  const [all, setAll] = useState(false);
  const { state, reload } = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), String(killed));
  useChatFocus(state.status === "ready" ? (state.data[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  const worth = (s: Suggestion) =>
    "expected_recovery_inr" in s.payload ? Number(s.payload.expected_recovery_inr) : 0;
  const sorted = [...state.data].sort((a, b) => worth(b) - worth(a));
  const shown = all ? sorted : sorted.slice(0, SHORT_LIST);
  return (
    <>
      <ul className="stack">
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
  return (
    <div className="stack">
      <h2>
        <Icon name="tick" /> {t("area.todo")}
      </h2>
      <p className="small">{t("area.todoNote")}</p>
      <Queue killed={killed} />
      <h2>
        <Icon name="chart" /> {t("area.scoreboard")}
      </h2>
      <Scores />
      <KillSwitch killed={killed} onChange={onKilledChange} />
    </div>
  );
}
