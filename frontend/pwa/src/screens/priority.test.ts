import { describe, expect, it } from "vitest";
import type { Suggestion } from "../api/types";
import { biggestFirst, worth } from "./priority";

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
