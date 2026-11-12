import { Icon } from "./Icons";
import { t } from "../i18n/strings";

/** Add whole days to an ISO date (YYYY-MM-DD) without any clock or time-zone surprises. */
export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Today's date on this phone, as YYYY-MM-DD. */
export function todayIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** A calendar to pick a past day: big arrows for the day before and after, and the date picker. */
export function CalendarPick({
  value,
  min,
  max,
  onChange,
}: {
  value: string;
  min: string;
  max: string;
  onChange: (iso: string) => void;
}) {
  return (
    <div className="cal" data-testid="calendar-pick">
      <button
        className="btn btn-plain"
        aria-label={t("cal.earlier")}
        disabled={value <= min}
        onClick={() => onChange(addDays(value, -1))}
      >
        <Icon name="back" size={32} />
      </button>
      <label className="cal-field">
        <Icon name="calendar" size={28} />
        <span className="sr-only">{t("cal.pick")}</span>
        <input
          type="date"
          value={value}
          min={min}
          max={max}
          onChange={(e) => {
            const v = e.target.value;
            if (v && v >= min && v <= max) onChange(v);
          }}
        />
      </label>
      <button
        className="btn btn-plain cal-next"
        aria-label={t("cal.later")}
        disabled={value >= max}
        onClick={() => onChange(addDays(value, 1))}
      >
        <Icon name="back" size={32} />
      </button>
    </div>
  );
}
