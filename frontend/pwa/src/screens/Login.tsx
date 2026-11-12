import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { LoginResponse, OrgChart } from "../api/types";
import { Icon } from "../components/Icons";
import { MAX_PIN_LENGTH, PIN_DOTS_SHOWN } from "../config";
import { t, type StringKey } from "../i18n/strings";

/** A big number pad. The PIN shows as dots, so no one has to read anything. */
export function Login({
  onSignedIn,
  notice,
}: {
  onSignedIn: (s: LoginResponse) => void;
  notice?: StringKey;
}) {
  const [pin, setPin] = useState("");
  const [problem, setProblem] = useState<StringKey | null>(notice ?? null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!pin || busy) return;
    setBusy(true);
    try {
      onSignedIn(await api.login(pin));
    } catch (error) {
      const status = error instanceof ApiError ? error.status : 0;
      setProblem(
        status === 429
          ? "login.tooMany"
          : status === 503
            ? "login.off"
            : status === 401
              ? "login.wrong"
              : "app.error",
      );
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
      <div className="login-wrap">
        <OrgTree />
        <div className="login-pin">
          <Icon name="lock" size={64} />
          <h2>{t("login.title")}</h2>
          <div className="pin-dots" role="img" aria-label={`${pin.length}`}>
            {Array.from(
              { length: Math.max(PIN_DOTS_SHOWN, pin.length) },
              (_, i) => (
                <span
                  key={i}
                  className={`dot ${i < pin.length ? "dot-on" : ""}`}
                />
              ),
            )}
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
            <button
              className="btn pad-key btn-no"
              onClick={() => setPin((p) => p.slice(0, -1))}
              aria-label={t("login.erase")}
            >
              <Icon name="back" size={36} />
            </button>
            <button className="btn pad-key" onClick={() => press("0")}>
              0
            </button>
            <button
              className="btn pad-key btn-yes"
              onClick={() => void submit()}
              disabled={!pin || busy}
              aria-label={t("login.enter")}
            >
              <Icon name="tick" size={36} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Who looks after which stores. Names only: no PINs and nothing to tap. */
function OrgTree() {
  const [chart, setChart] = useState<OrgChart | null>(null);
  useEffect(() => {
    api.orgChart().then(setChart, () => setChart(null));
  }, []);
  if (!chart || chart.areas.length === 0) return null;
  return (
    <div className="org" data-testid="org-tree">
      <h3>{t("org.title")}</h3>
      <div className="org-node org-top">
        <Icon name="box" size={28} />
        <span>
          <b>{t("role.dc_lead")}</b>
          <small>{t("org.dc")}</small>
        </span>
      </div>
      <ul className="org-areas">
        {chart.areas.map((area) => (
          <li key={area.area_id}>
            <div className="org-node">
              <Icon name="chart" size={28} />
              <span>
                <b>{`${t("role.area_manager")}: ${area.name}`}</b>
                <small>{`${area.stores.length} ${area.stores.length === 1 ? t("org.store") : t("org.stores")}`}</small>
              </span>
            </div>
            <ul className="org-stores">
              {area.stores.map((s) => (
                <li key={s.store_id}>
                  <Icon name="store" size={20} />
                  <span>
                    {s.place ? `${s.store_id} · ${s.place}` : s.store_id}
                  </span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <div className="org-node org-side">
        <Icon name="tractor" size={28} />
        <span>
          <b>{t("role.farmer_coordinator")}</b>
          <small>{t("org.farmer")}</small>
        </span>
      </div>
    </div>
  );
}
