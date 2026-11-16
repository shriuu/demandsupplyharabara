import { api } from "../api/client";
import { useLoad } from "../api/useApi";
import type { Targets } from "../api/types";
import { t, type StringKey } from "../i18n/strings";
import { Icon, type IconName } from "./Icons";

const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 10) / 10}%`);

/** The brief's targets, from config on the server. Null while loading or if they cannot be read. */
export function useTargets(): Targets | null {
  const { state } = useLoad(() => api.targets(), []);
  return state.status === "ready" ? state.data : null;
}

/** A scale that makes small values visible, and always has room for the markers. */
function scaleMax(values: (number | null)[]): number {
  const biggest = Math.max(0, ...values.filter((v): v is number => v !== null));
  return Math.max(10, Math.ceil((biggest * 1.25) / 5) * 5);
}

type Kind = "on" | "near" | "above" | "unknown";

/** One measure where lower is better (thrown away, ran out): a bar, a target mark, and all stores for comparison. */
export function Measure({
  label,
  icon,
  value,
  target,
  nearLimit,
  allStores,
}: {
  label: StringKey;
  icon: IconName;
  value: number | null;
  target: number | null;
  nearLimit?: number | null;
  allStores?: number | null;
}) {
  const max = scaleMax([value, target, nearLimit ?? null, allStores ?? null]);
  const at = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const kind: Kind =
    value === null || target === null ? "unknown" : value <= target ? "on" : nearLimit != null && value <= nearLimit ? "near" : "above";
  const word = t(`measure.${kind}` as StringKey);
  return (
    <div className="measure" data-testid="measure" data-kind={kind}>
      <div className="measure-head">
        <Icon name={icon} size={26} />
        <span className="measure-name">{t(label)}</span>
        <strong className="measure-value">{pct(value)}</strong>
        <span className={`measure-state state-${kind}`}>
          <Icon name={kind === "on" ? "tick" : kind === "unknown" ? "clock" : "alert"} size={20} /> {word}
        </span>
      </div>
      <div className="measure-track" role="img" aria-label={`${t(label)} ${pct(value)}. ${word}.`}>
        {value !== null && <div className="measure-fill" style={{ width: at(value) }} />}
        {target !== null && <span className="measure-mark mark-target" style={{ left: at(target) }} />}
        {allStores != null && <span className="measure-mark mark-all" style={{ left: at(allStores) }} />}
      </div>
      <p className="measure-legend small">
        {target !== null && (
          <span>
            <span className="key key-target" /> {t("measure.target", { pct: pct(target) })}
          </span>
        )}
        {allStores != null && (
          <span>
            <span className="key key-all" /> {t("measure.all", { pct: pct(allStores) })}
          </span>
        )}
      </p>
    </div>
  );
}

/** Thrown away and ran out, always together, each against its target and against all stores. */
export function ThrownAwayAndRanOut({
  waste,
  out,
  allWaste,
  allOut,
}: {
  waste: number | null;
  out: number | null;
  allWaste?: number | null;
  allOut?: number | null;
}) {
  const targets = useTargets();
  return (
    <div className="measures" data-testid="measures">
      <Measure label="score.waste" icon="bag" value={waste} target={targets?.waste_pct_max ?? null} allStores={allWaste} />
      <Measure
        label="score.stockout"
        icon="box"
        value={out}
        target={targets?.stockout_pct_ideal ?? null}
        nearLimit={targets?.stockout_pct_hard_max ?? null}
        allStores={allOut}
      />
    </div>
  );
}
