import { t } from "../i18n/strings";
import type { Range } from "../api/types";

/** Low-to-high band on a shared scale with a marker at the likely value, digits beside. */
export function RangeBar({ range, max, unit = "" }: { range: Range; max: number; unit?: string }) {
  const pct = (n: number) => `${(n / max) * 100}%`;
  return (
    <div className="rangebar">
      <div className="rangebar-track" aria-hidden="true">
        <div className="rangebar-band" style={{ left: pct(range.low), width: pct(range.high - range.low) }} />
        <div className="rangebar-mark" style={{ left: pct(range.likely) }} />
      </div>
      <p className="digits">
        <strong>{t("range.likely", { n: Math.round(range.likely), unit })}</strong>{" "}
        <small>{t("range.band", { low: Math.round(range.low), high: Math.round(range.high), unit })}</small>
      </p>
    </div>
  );
}
