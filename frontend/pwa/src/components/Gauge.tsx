import { t, type StringKey } from "../i18n/strings";
import { Icon, type IconName } from "./Icons";

/** A half-dial gauge. `value` is a percentage 0..100, or null when not known (never guessed). */
export function Gauge({
  label,
  icon,
  value,
  goodWhen,
}: {
  label: StringKey;
  icon: IconName;
  value: number | null;
  goodWhen: "low" | "high";
}) {
  const known = value !== null;
  const pct = known ? Math.min(100, Math.max(0, value)) : 0;
  const arc = Math.PI * 40;
  const bad = known && (goodWhen === "low" ? pct > 10 : pct < 50);
  return (
    <div className="gauge" data-known={known}>
      <svg viewBox="0 0 100 58" width="100%" role="img" aria-label={t(label)}>
        <path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="#e0e6d6" strokeWidth="10" strokeLinecap="round" />
        {known && (
          <path
            d="M10 50 A40 40 0 0 1 90 50"
            fill="none"
            stroke={bad ? "#c62828" : "#2f7d32"}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${(arc * pct) / 100} ${arc}`}
          />
        )}
      </svg>
      <Icon name={icon} size={26} />
      <strong className="gauge-value">{known ? `${Math.round(pct * 10) / 10}%` : t("score.unknown")}</strong>
      <span className="gauge-label">{t(label)}</span>
    </div>
  );
}
