import { ACTOR_ID_PREFIX, API_BASE } from "../config";
import type {
  Approval,
  AskResponse,
  DcTotals,
  FarmerVolumeForecast,
  Health,
  PriceQuote,
  Role,
  Scorecard,
  Suggestion,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) throw new ApiError(response.status, `${response.status} ${path}`);
  return (await response.json()) as T;
}

function query(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request<Health>("/health"),
  suggestions: (params: {
    role: Role;
    store_id?: string;
    kind?: string;
    state?: string;
  }) => request<Suggestion[]>(`/suggestions${query(params)}`),
  decide: (
    role: Role,
    suggestionId: string,
    body: { action: Approval["action"]; edited_units?: number; reason?: string },
  ) => {
    const approval: Approval = {
      suggestion_id: suggestionId,
      actor_role: role,
      actor_id: `${ACTOR_ID_PREFIX}${role}`,
      at: new Date().toISOString(),
      ...body,
    };
    return request<Suggestion>(`/suggestions/${encodeURIComponent(suggestionId)}/decision`, {
      method: "POST",
      body: JSON.stringify(approval),
    });
  },
  dcTotals: () => request<DcTotals>("/dc/totals"),
  prices: () => request<PriceQuote[]>("/prices"),
  farmers: (fpoId?: string) =>
    request<FarmerVolumeForecast[]>(`/farmers/forecast${query({ fpo_id: fpoId })}`),
  scorecard: () => request<Scorecard[]>("/scorecard"),
  killSwitch: () =>
    request<Health>("/admin/kill-switch", { method: "POST", body: JSON.stringify({ active: true }) }),
  ask: (suggestionId: string, question: string) =>
    request<AskResponse>("/assistant/ask", {
      method: "POST",
      body: JSON.stringify({ suggestion_id: suggestionId, question }),
    }),
};
