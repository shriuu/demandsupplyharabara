// Contract types come from harabhara/contracts.py (see scripts/gen-types.mjs).
// Response wrappers the contract file does not define are declared here and listed in
// frontend/pwa/README.md so the API session can match them.
import type {
  Approval,
  AuditEvent,
  FarmerVolumeForecast,
  Forecast,
  MarkdownPayload,
  OrderPayload,
  PriceQuote,
  Range,
  Scorecard,
  Suggestion,
  SurplusPayload,
  TransferPayload,
} from "./contracts";

export type {
  Approval,
  AuditEvent,
  FarmerVolumeForecast,
  Forecast,
  MarkdownPayload,
  OrderPayload,
  PriceQuote,
  Range,
  Scorecard,
  Suggestion,
  SurplusPayload,
  TransferPayload,
};

export type Role = Suggestion["approver_role"];
export type Driver = Suggestion["drivers"][number];

export interface Health {
  status: string;
  kill_switch: boolean;
}

/** One line of `GET /dc/totals`: the nightly order total for a product, with its range. */
export interface DcTotal {
  sku_id: string;
  total: Range;
}

/** A suggestion to the DC buying lead: buy less on the spot (mandi) market first. Info only. */
export interface TrimSuggestion {
  suggestion_id: string;
  sku_id: string;
  reduce_spot_units: number;
  reason: string;
}

export interface DcTotals {
  date: string;
  totals: DcTotal[];
  trimming: TrimSuggestion[];
}

export interface AskResponse {
  answer: string | null;
}
