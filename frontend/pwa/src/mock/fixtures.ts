// Small synthetic fixtures typed from the contracts. No real data.
import type {
  DcTotals,
  FarmerVolumeForecast,
  PriceQuote,
  Scorecard,
  Suggestion,
} from "../api/types";

const base = {
  model_version: "mock-1",
  data_snapshot_id: "mock-snapshot",
  config_digest: "mock-config",
  created_at: "2026-11-03T18:00:00+05:30",
  deadline: "2026-11-03T21:00:00+05:30",
  state: "proposed" as const,
};

export function suggestions(): Suggestion[] {
  return [
    {
      ...base,
      id: "s-order-tomato",
      store_id: "S01",
      sku_id: "TOMATO",
      approver_role: "store_manager",
      reason: "Rain is coming tomorrow, so fewer shoppers will visit.",
      drivers: [{ kind: "weather", direction: "down", code: "heavy_rain_walk_in", detail: "rain" }],
      payload: {
        kind: "order",
        recommended_units: 8,
        range: { low: 6, likely: 8, high: 11 },
        manager_rule_units: 10,
      },
    },
    {
      ...base,
      id: "s-order-banana",
      store_id: "S01",
      sku_id: "BANANA",
      approver_role: "store_manager",
      reason: "Diwali eve is tomorrow, so more shoppers will want bananas.",
      drivers: [{ kind: "festival", direction: "up", code: "festival_eve", detail: "Diwali eve" }],
      payload: {
        kind: "order",
        recommended_units: 20,
        range: { low: 16, likely: 20, high: 26 },
        manager_rule_units: 18,
      },
    },
    {
      ...base,
      id: "s-order-spinach",
      store_id: "S01",
      sku_id: "SPINACH",
      approver_role: "store_manager",
      reason: "Spinach will not last past tomorrow, so order a little less.",
      drivers: [{ kind: "shelf_life", direction: "down", code: "short_life", detail: "1 sellable day" }],
      payload: {
        kind: "order",
        recommended_units: 5,
        range: { low: 3, likely: 5, high: 7 },
        manager_rule_units: null,
      },
    },
    {
      ...base,
      id: "s-mark-spinach",
      store_id: "S01",
      sku_id: "SPINACH",
      created_at: "2026-11-04T06:00:00+05:30",
      deadline: "2026-11-04T09:00:00+05:30",
      approver_role: "store_manager",
      reason: "Some spinach will be left over, so sell it cheaper from afternoon.",
      drivers: [{ kind: "stock_age", direction: "none", code: "wont_last", detail: "1 day left" }],
      payload: {
        kind: "markdown",
        units: 3,
        step_pct: 15,
        start: "15:00",
        expected_recovery_inr: 120,
        earlier_than_last_day: true,
      },
    },
    {
      ...base,
      id: "s-transfer-mango",
      store_id: "S01",
      sku_id: "MANGO",
      created_at: "2026-11-04T06:00:00+05:30",
      deadline: "2026-11-04T08:00:00+05:30",
      approver_role: "store_manager",
      reason: "Mango may sell out by noon, and the next store has extra.",
      drivers: [{ kind: "recent_sellout", direction: "up", code: "early_sellout", detail: "" }],
      payload: { kind: "transfer", from_store: "S02", to_store: "S01", units: 4, leave_by: "08:00", van_cost_inr: 150 },
    },
    {
      ...base,
      id: "s-surplus-onion",
      store_id: "S01",
      sku_id: "ONION",
      created_at: "2026-11-04T06:00:00+05:30",
      deadline: "2026-11-04T16:00:00+05:30",
      approver_role: "store_manager",
      reason: "Onions will be left over, and this buyer can pick them up.",
      drivers: [{ kind: "rule", direction: "none", code: "surplus_match", detail: "" }],
      payload: {
        kind: "surplus",
        buyer_id: "B1",
        units: 6,
        grade: "B",
        pickup_window: "17:00 to 18:00",
        expected_recovery_inr: 240,
      },
    },
    {
      ...base,
      id: "s-area-transfer",
      store_id: "S03",
      sku_id: "TOMATO",
      approver_role: "area_manager",
      reason: "Tomatoes may sell out in store S03, and store S02 has extra.",
      drivers: [{ kind: "recent_sellout", direction: "up", code: "early_sellout", detail: "" }],
      payload: { kind: "transfer", from_store: "S02", to_store: "S03", units: 5, leave_by: "08:30", van_cost_inr: 150 },
    },
    {
      ...base,
      id: "s-area-markdown",
      store_id: "S02",
      sku_id: "BANANA",
      approver_role: "area_manager",
      reason: "Bananas are ripening fast, so start the cheaper price early.",
      drivers: [{ kind: "shelf_life", direction: "down", code: "short_life", detail: "" }],
      payload: {
        kind: "markdown",
        units: 7,
        step_pct: 15,
        start: "14:00",
        expected_recovery_inr: 210,
        earlier_than_last_day: true,
      },
    },
  ];
}

const meta = { stores: 3, flags: [] as never[], demand_estimated: false, model_version: "mock-1", data_snapshot_id: "mock-snapshot", config_digest: "mock-config" };

export const dcTotals: DcTotals = {
  on: "2026-11-04",
  totals: [
    { ...meta, sku_id: "TOMATO", demand: { low: 40, likely: 52, high: 64 } },
    { ...meta, sku_id: "BANANA", demand: { low: 80, likely: 96, high: 120 } },
    { ...meta, sku_id: "SPINACH", demand: { low: 15, likely: 22, high: 30 } },
  ],
  trimming: [
    { sku_id: "TOMATO", spot_units_to_trim: 6, reason: "Stock is long for tomatoes, so buy less at the mandi first." },
  ],
  stale: false,
};

const fetched_at = "2026-11-03T17:00:00+05:30";
export const prices: PriceQuote[] = [
  {
    sku_id: "TOMATO",
    market: "Synthetic Mandi",
    on: "2026-11-03",
    modal_inr: 28,
    min_inr: 22,
    max_inr: 34,
    source: "Mock price feed (synthetic)",
    fetched_at,
    status: "ok",
  },
  {
    sku_id: "BANANA",
    market: "Synthetic Mandi",
    on: "2026-11-01",
    modal_inr: 41,
    min_inr: null,
    max_inr: null,
    source: "Mock price feed (synthetic)",
    fetched_at,
    status: "stale",
  },
  {
    sku_id: "SPINACH",
    market: "Synthetic Mandi",
    on: "2026-11-03",
    modal_inr: null,
    min_inr: null,
    max_inr: null,
    source: "Mock price feed (synthetic)",
    fetched_at,
    status: "unavailable",
  },
];

export const farmerForecast: FarmerVolumeForecast[] = ["TOMATO", "BANANA"].flatMap((sku, i) =>
  ["2026-11-04", "2026-11-05", "2026-11-06"].map((on, d) => ({
    fpo_id: "FPO1",
    sku_id: sku,
    on,
    volume: { low: 30 + i * 20 + d * 2, likely: 40 + i * 20 + d * 3, high: 55 + i * 20 + d * 4 },
    label: "estimate" as const,
  })),
);

export const scorecards: Scorecard[] = [
  {
    scope: "All stores",
    period_start: "2026-10-01",
    period_end: "2026-10-31",
    waste_pct: 6.2,
    stockout_pct: 3.1,
    farmer_share: 0.62,
    farmer_share_definition: "Share of purchases from farmer groups (mock)",
  },
];
