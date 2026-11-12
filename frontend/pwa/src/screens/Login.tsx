import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { DemoAccount, DemoAccounts, LoginResponse } from "../api/types";
import { Icon } from "../components/Icons";
import { MAX_PIN_LENGTH, PIN_DOTS_SHOWN } from "../config";
import { t, type StringKey } from "../i18n/strings";

/** A big number pad. The PIN shows as dots, so no one has to read anything. */
export function Login({ onSignedIn, notice }: { onSignedIn: (s: LoginResponse) => void; notice?: StringKey }) {
  const [pin, setPin] = useState("");
  const [problem, setProblem] = useState<StringKey | null>(notice ?? null);
  const [busy, setBusy] = useState(false);

  async function submit(withPin = pin) {
    if (!withPin || busy) return;
    setBusy(true);
    try {
      onSignedIn(await api.login(withPin));
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      setProblem(status === 429 ? "login.tooMany" : status === 503 ? "login.off" : status === 401 ? "login.wrong" : "app.error");
      setPin("");
    }
    setBusy(false);
  }

  const press = (digit: string) => {
    setProblem(null);
    setPin((p) => (p.length < MAX_PIN_LENGTH ? p + digit : p));
  };

  return (
    <section className="login" aria-label={t("login.title")}>
      <DemoSignIns onPick={(p) => void submit(p)} />
      <Icon name="lock" size={64} />
      <h2>{t("login.title")}</h2>
      <div className="pin-dots" role="img" aria-label={`${pin.length}`}>
        {Array.from({ length: Math.max(PIN_DOTS_SHOWN, pin.length) }, (_, i) => (
          <span key={i} className={`dot ${i < pin.length ? "dot-on" : ""}`} />
        ))}
      </div>
      {problem && (
        <p className="notice notice-error" role="alert">
          <Icon name="alert" /> {t(problem)}
        </p>
      )}
      <div className="pad">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} className="btn pad-key" onClick={() => press(d)}>
            {d}
          </button>
        ))}
        <button className="btn pad-key btn-no" onClick={() => setPin((p) => p.slice(0, -1))} aria-label={t("login.erase")}>
          <Icon name="back" size={36} />
        </button>
        <button className="btn pad-key" onClick={() => press("0")}>
          0
        </button>
        <button className="btn pad-key btn-yes" onClick={() => void submit()} disabled={!pin || busy} aria-label={t("login.enter")}>
          <Icon name="tick" size={36} />
        </button>
      </div>
    </section>
  );
}

/**
 * For an online trial only: the server lists the sample sign-ins when it is switched on, and says
 * nothing (404) when it is not, so a real deployment shows none of this. Drawn as a small tree:
 * stores report to their area manager, area managers to the DC buying lead.
 */
function DemoSignIns({ onPick }: { onPick: (pin: string) => void }) {
  const [demo, setDemo] = useState<DemoAccounts | null>(null);
  useEffect(() => {
    api.demoAccounts().then(setDemo, () => setDemo(null));
  }, []);
  if (!demo || demo.accounts.length === 0) return null;

  const of = (role: DemoAccount["role"]) => demo.accounts.filter((a) => a.role === role);
  const stores = of("store_manager");
  const areaManagers = of("area_manager");

  return (
    <div className="demo" data-testid="demo-sign-ins">
      <h3>{t("demo.title")}</h3>
      <p className="demo-note">{t("demo.note")}</p>
      {of("dc_lead").map((a) => (
        <Card key={a.pin} a={a} icon="box" title={t("role.dc_lead")} sub={t("demo.dc")} onPick={onPick} top />
      ))}
      <ul className="demo-tree">
        {areaManagers
          .filter((a) => !a.area_id)
          .map((a) => (
            <li key={a.pin}>
              <Card a={a} icon="chart" title={t("demo.allAreas")} sub={t("demo.allAreasNote")} onPick={onPick} />
            </li>
          ))}
        {Object.entries(demo.areas).map(([areaId, areaName]) => (
          <li key={areaId} className="demo-area">
            {areaManagers
              .filter((a) => a.area_id === areaId)
              .map((a) => (
                <Card key={a.pin} a={a} icon="chart" title={`${t("role.area_manager")}: ${areaName}`} sub={t("demo.stores")} onPick={onPick} />
              ))}
            <ul className="demo-stores">
              {stores
                .filter((s) => s.area_id === areaId)
                .map((s) => (
                  <li key={s.pin}>
                    <Card a={s} icon="store" title={s.store_id ?? ""} sub={s.place ?? ""} onPick={onPick} />
                  </li>
                ))}
            </ul>
          </li>
        ))}
      </ul>
      {of("farmer_coordinator").map((a) => (
        <Card key={a.pin} a={a} icon="tractor" title={t("role.farmer_coordinator")} sub={t("demo.farmer")} onPick={onPick} side />
      ))}
    </div>
  );
}

function Card({ a, icon, title, sub, onPick, top, side }: {
  a: DemoAccount;
  icon: "box" | "chart" | "store" | "tractor";
  title: string;
  sub: string;
  onPick: (pin: string) => void;
  top?: boolean;
  side?: boolean;
}) {
  return (
    <button className={`demo-card ${top ? "demo-top" : ""} ${side ? "demo-side" : ""}`} onClick={() => onPick(a.pin)}>
      <Icon name={icon} size={32} />
      <span>
        <b>{title}</b>
        <small>{sub}</small>
      </span>
      <span className="demo-pin" aria-label={`${t("demo.pin")} ${a.pin}`}>{a.pin}</span>
    </button>
  );
}
