/** A whole number typed with the phone's number pad. Anything that is not a digit is dropped. */
const MAX_DIGITS = 6;

export function NumberField({
  label,
  value,
  onChange,
  unit,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  unit?: string;
}) {
  return (
    <span className="number-field">
      <input
        className="field number-input"
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        autoComplete="off"
        aria-label={label}
        value={String(value)}
        onFocus={(e) => e.currentTarget.select()}
        onChange={(e) => {
          const digits = e.target.value.replace(/\D/g, "").slice(0, MAX_DIGITS);
          onChange(digits === "" ? 0 : Number(digits));
        }}
      />
      {unit && <small>{unit}</small>}
    </span>
  );
}
