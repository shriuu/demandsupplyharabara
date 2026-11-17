import type { Suggestion } from "../api/types";
import { t } from "../i18n/strings";
import { Icon } from "./Icons";

/**
 * Why, for an alert row. A discount says it in a few words (the last sellable day, or an early start);
 * the full one-sentence reason stays stored on the suggestion and is read aloud / asked about in Ask.
 * Anything else (a store-to-store move) keeps its sentence behind a small "Why".
 */
export function WhyLine({ suggestion }: { suggestion: Suggestion }) {
  const p = suggestion.payload;
  if (p.kind === "markdown") {
    return (
      <span className="chip chip-soft" data-testid="why-chip">
        <Icon name="clock" size={18} /> {t(p.earlier_than_last_day ? "alert.earlier" : "alert.lastDay")}
      </span>
    );
  }
  return (
    <details className="dc-why">
      <summary>{t("dc.why")}</summary>
      <p className="small">{suggestion.reason}</p>
    </details>
  );
}
