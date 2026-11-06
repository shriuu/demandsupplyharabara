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

/** One decision for a person: a product's markdown steps are one card, everything else stands alone. */
export type Group = { key: string; items: Suggestion[] };

/**
 * The playbook's markdown ladder (30% off, then 50% off in the evening) arrives as one suggestion
 * per step. Showing each step as its own card repeats the product; a person decides the ladder once.
 * Each step is still its own suggestion, approved and logged on its own.
 */
export function groupSteps(list: Suggestion[]): Group[] {
  const groups = new Map<string, Group>();
  for (const s of list) {
    const key = s.payload.kind === "markdown" ? `markdown:${s.store_id}:${s.sku_id}` : s.id;
    const group = groups.get(key);
    if (group) group.items.push(s);
    else groups.set(key, { key, items: [s] });
  }
  const startOf = (s: Suggestion) => ("start" in s.payload ? String(s.payload.start) : "");
  const stepOf = (s: Suggestion) => ("step_pct" in s.payload ? Number(s.payload.step_pct) : 0);
  for (const g of groups.values()) g.items.sort((a, b) => startOf(a).localeCompare(startOf(b)) || stepOf(a) - stepOf(b));
  return [...groups.values()];
}

export const groupWorth = (g: Group): number => g.items.reduce((sum, s) => sum + worth(s), 0);
export const biggestGroupFirst = (a: Group, b: Group): number => groupWorth(b) - groupWorth(a);
