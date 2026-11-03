import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { MarkdownPayload, Scorecard, Suggestion, TransferPayload } from "../api/types";
import { Confirm, TickCross } from "../components/Buttons";
import { useChatFocus } from "../components/chatContext";
import { Gauge } from "../components/Gauge";
import { Icon } from "../components/Icons";
import { ProductIcon } from "../components/ProductIcon";
import { Empty, Loading, LoadError } from "../components/Status";
import { productName, t } from "../i18n/strings";

/** Waste, empty shelves and farmer share: always the same three gauges, side by side (G04). */
export function Scoreboard({ card }: { card: Scorecard }) {
  return (
    <section className="card scoreboard" aria-label={t("area.scoreboard")} data-scope={card.scope}>
      <h3>{card.scope}</h3>
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

function Scores() {
  const { state, reload } = useLoad(() => api.scorecard(), []);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  return (
    <>
      {state.data.map((c) => (
        <Scoreboard key={c.scope} card={c} />
      ))}
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
            {productName(s.sku_id)} · {s.store_id}
          </h3>
          {!("to_store" in p) ? (
            <p>
              <Icon name="tag" size={22} /> {t("alert.markdownDetail", { pct: p.step_pct, start: p.start })}
            </p>
          ) : (
            <p>
              <Icon name="van" size={22} /> {t("alert.transferDetail", { units: p.units, store: p.to_store, time: p.leave_by })}
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
  const { state, reload } = useLoad(() => api.suggestions({ role: "area_manager", state: "proposed" }), String(killed));
  useChatFocus(state.status === "ready" ? (state.data[0]?.id ?? null) : null);
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") return <LoadError onRetry={reload} />;
  if (!state.data.length) return <Empty />;
  return (
    <ul className="stack">
      {state.data.map((s) => (
        <ApprovalCard key={s.id} s={s} onDone={reload} />
      ))}
    </ul>
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
        <Icon name="chart" /> {t("area.scoreboard")}
      </h2>
      <Scores />
      <h2>
        <Icon name="tick" /> {t("area.queue")}
      </h2>
      <Queue killed={killed} />
      <KillSwitch killed={killed} onChange={onKilledChange} />
    </div>
  );
}
