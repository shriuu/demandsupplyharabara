import { t, type StringKey } from "../i18n/strings";
import { Icon } from "./Icons";

export type Light = "red" | "amber" | "green";

const labels: Record<Light, StringKey> = { red: "alert.red", amber: "alert.amber", green: "action.done" };

/** Traffic light: colour is always paired with a shape/icon and a word (never colour alone). */
export function TrafficLight({ light }: { light: Light }) {
  return (
    <span className={`light light-${light}`} data-light={light}>
      <Icon name={light === "red" ? "stop" : light === "amber" ? "alert" : "tick"} size={26} />
      <span className="light-word">{t(labels[light])}</span>
    </span>
  );
}

export function Loading() {
  return (
    <p className="notice" role="status">
      <Icon name="hourglass" /> {t("app.loading")}
    </p>
  );
}

export function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="notice notice-error" role="alert">
      <Icon name="alert" /> <span>{t("app.error")}</span>
      <button className="btn btn-plain" onClick={onRetry}>
        {t("app.retry")}
      </button>
    </div>
  );
}

export function Empty() {
  return (
    <p className="notice" role="status">
      <Icon name="tick" /> {t("app.nothing")}
    </p>
  );
}
