import { Icon } from "./Icons";
import { NumberField } from "./NumberField";
import { t } from "../i18n/strings";

/** A number you change with big plus and minus buttons; the digits are small beside them. */
export function Counter({
  label,
  value,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="counter" role="group" aria-label={label}>
      <p className="counter-label">{label}</p>
      <div className="stepper">
        <button
          className="btn btn-step"
          aria-label={`${label}: ${t("action.minus")}`}
          disabled={value <= 0}
          onClick={() => onChange(Math.max(0, value - step))}
        >
          <Icon name="minus" size={36} />
        </button>
        <NumberField label={label} value={value} onChange={onChange} unit={unit} />
        <button className="btn btn-step" aria-label={`${label}: ${t("action.plus")}`} onClick={() => onChange(value + step)}>
          <Icon name="plus" size={36} />
        </button>
      </div>
    </div>
  );
}
