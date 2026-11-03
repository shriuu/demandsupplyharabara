import { MAX_ICONS } from "../config";
import { t } from "../i18n/strings";
import type { Range } from "../api/types";
import { Icon } from "./Icons";

/** Quantity as a row of crates: solid up to the order, lighter for the less-or-more band. */
export function Crates({ units, range }: { units: number; range: Range }) {
  const perIcon = Math.max(1, Math.ceil(range.high / MAX_ICONS));
  const solid = Math.round(units / perIcon);
  const bandLow = Math.min(solid, Math.round(range.low / perIcon));
  const bandHigh = Math.max(solid, Math.round(range.high / perIcon));
  const cells = Array.from({ length: bandHigh }, (_, i) => {
    const kind = i < bandLow ? "full" : i < solid ? "maybe-in" : "maybe";
    return (
      <span key={i} className={`crate crate-${kind}`} data-kind={kind}>
        <Icon name="crate" size={32} filled={kind === "full"} />
      </span>
    );
  });
  return (
    <div className="crates" role="img" aria-label={t("order.units", { n: units })}>
      <div className="crate-row">{cells}</div>
      <p className="digits">
        <strong>{units}</strong> <small>{t("order.range", { low: range.low, high: range.high })}</small>
      </p>
    </div>
  );
}
