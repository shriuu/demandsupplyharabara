import { describe, expect, it } from "vitest";
import type { ProductSeries, Targets } from "../api/types";
import { bigger } from "./ProductDashboard";

const targets = { waste_pct_max: 5.5, stockout_pct_ideal: 7, stockout_pct_hard_max: 9.1 } as Targets;
const p = (o: Partial<ProductSeries>) =>
  ({ sku_id: "P01", days: [], days_counted: 7, days_ran_out: 0, units_wasted: 0, units_sold: 100, waste_pct: 0, average_left: 5, latest_left: 5, ...o }) as ProductSeries;

describe("which problem is bigger for a product over the week", () => {
  it("is none when nothing was thrown away and it never ran out", () => {
    expect(bigger(p({}), targets)).toBe("none");
  });
  it("is ran out when it ran out and little was thrown away", () => {
    expect(bigger(p({ days_ran_out: 2, units_wasted: 1, waste_pct: 1 }), targets)).toBe("ran");
  });
  it("is thrown away when much was binned and it ran out only once", () => {
    expect(bigger(p({ days_ran_out: 1, units_wasted: 30, waste_pct: 20 }), targets)).toBe("wasted");
  });
  it("shows only one even when both happened", () => {
    expect(["ran", "wasted"]).toContain(bigger(p({ days_ran_out: 1, units_wasted: 5, waste_pct: 5 }), targets));
  });
});
