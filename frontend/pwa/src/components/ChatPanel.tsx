import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { Role } from "../api/types";
import { productName, t } from "../i18n/strings";
import { Icon } from "./Icons";

interface Turn {
  question: string;
  answer: string;
}

/** Asks the assistant about one stored suggestion. It can explain, never decide. */
export function ChatPanel({ role, focusId }: { role: Role; focusId: string | null }) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const list = useLoad(() => api.suggestions({ role }), [role]);
  const id = focusId ?? picked;

  async function send() {
    const question = text.trim();
    if (!question || !id) return;
    setBusy(true);
    setText("");
    let answer = t("chat.unknown");
    try {
      const response = await api.ask(id, question);
      if (response.answer) answer = response.answer;
    } catch {
      // Any failure shows the safe answer rather than a guess.
    }
    setTurns((previous) => [...previous, { question, answer }]);
    setBusy(false);
  }

  if (!open) {
    return (
      <button className="chat-fab btn" onClick={() => setOpen(true)} aria-label={t("chat.open")}>
        <Icon name="chat" size={34} />
        <span>{t("chat.open")}</span>
      </button>
    );
  }
  const choices = list.state.status === "ready" ? list.state.data : [];
  return (
    <section className="chat" aria-label={t("chat.title")}>
      <header className="chat-head">
        <strong>{t("chat.title")}</strong>
        <button className="btn btn-plain" onClick={() => setOpen(false)} aria-label={t("chat.close")}>
          <Icon name="cross" size={28} />
        </button>
      </header>
      {!focusId && (
        <select
          className="field"
          value={picked ?? ""}
          onChange={(e) => setPicked(e.target.value || null)}
          aria-label={t("chat.pick")}
        >
          <option value="">{t("chat.pick")}</option>
          {choices.map((s) => (
            <option key={s.id} value={s.id}>
              {productName(s.sku_id)} · {s.payload.kind}
            </option>
          ))}
        </select>
      )}
      {!id && !choices.length && <p className="notice">{t("chat.none")}</p>}
      <ul className="chat-log" aria-live="polite">
        {turns.map((turn, i) => (
          <li key={i}>
            <p className="chat-q">{turn.question}</p>
            <p className="chat-a">{turn.answer}</p>
          </li>
        ))}
        {busy && <li className="chat-a">{t("chat.thinking")}</li>}
      </ul>
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          className="field"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
          disabled={!id}
        />
        <button className="btn btn-yes btn-small" type="submit" disabled={!id || busy} aria-label={t("chat.send")}>
          <Icon name="send" size={28} />
        </button>
      </form>
    </section>
  );
}
