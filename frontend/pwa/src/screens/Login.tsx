import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { LoginResponse } from "../api/types";
import { Icon } from "../components/Icons";
import { MAX_PIN_LENGTH, PIN_DOTS_SHOWN } from "../config";
import { t, type StringKey } from "../i18n/strings";

/** A big number pad. The PIN shows as dots, so no one has to read anything. */
export function Login({ onSignedIn, notice }: { onSignedIn: (s: LoginResponse) => void; notice?: StringKey }) {
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
