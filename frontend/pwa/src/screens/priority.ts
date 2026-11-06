import type { Suggestion } from "../api/types";

/** How much is at stake, for ordering tiles: biggest first. */
export function worth(s: Suggestion): number {
  const p = s.payload;
  if ("expected_recovery_inr" in p) return Number(p.expected_recovery_inr);
  if ("recommended_units" in p) return Number(p.recommended_units);
  if ("units" in p) return Number(p.units);
  return 0;
}

export const biggestFirst = (a: Suggestion, b: Suggestion): number => worth(b) - worth(a);
