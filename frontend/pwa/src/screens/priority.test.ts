import { describe, expect, it } from "vitest";
import type { Suggestion } from "../api/types";
import { biggestFirst, groupSteps, groupWorth, worth, type Group } from "./priority";

const make = (payload: object) => ({ payload }) as unknown as Suggestion;

describe("priority", () => {
  it("counts money for markdowns, crates for orders and units for transfers", () => {
    expect(worth(make({ kind: "markdown", expected_recovery_inr: 240 }))).toBe(240);
    expect(worth(make({ kind: "order", recommended_units: 20 }))).toBe(20);
    expect(worth(make({ kind: "transfer", units: 4 }))).toBe(4);
  });

  it("puts the biggest first", () => {
    const list = [make({ kind: "order", recommended_units: 5 }), make({ kind: "order", recommended_units: 20 })];
    expect([...list].sort(biggestFirst).map(worth)).toEqual([20, 5]);
  });
});

describe("groupSteps", () => {
  const step = (id: string, store: string, sku: string, pct: number, start: string, kind = "markdown") =>
    ({ id, store_id: store, sku_id: sku, payload: { kind, step_pct: pct, start, expected_recovery_inr: 10 } }) as unknown as Suggestion;

  it("puts one product's markdown steps on one card, in time order, and leaves others alone", () => {
    const list = [
      step("a2", "S08", "spinach", 50, "18:00"),
      step("a1", "S08", "spinach", 30, "07:00"),
      step("b1", "S08", "tomato", 30, "07:00"),
      step("c1", "S09", "spinach", 30, "07:00"),
      step("t1", "S08", "tomato", 0, "08:00", "transfer"),
    ];
    const groups = groupSteps(list);
    expect(groups.map((g) => g.items.map((s) => s.id))).toEqual([["a1", "a2"], ["b1"], ["c1"], ["t1"]]);
  });

  it("counts the whole ladder when ordering", () => {
    const groups = groupSteps([step("a1", "S08", "spinach", 30, "07:00"), step("a2", "S08", "spinach", 50, "18:00")]);
    expect(groupWorth(groups[0] as Group)).toBe(20);
  });
});
