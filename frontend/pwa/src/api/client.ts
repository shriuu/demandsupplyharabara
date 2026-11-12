import { API_BASE } from "../config";
import { clearSession, loadSession, saveSession, signalExpired, signalSwitchedOff } from "./session";
import type {
  DayView,
  FarmerDay,
  HistorySeries,
  OrgChart,
  Approval,
  AskResponse,
  DcOrders,
  DcTotals,
  FarmerVolumeForecast,
  Health,
  KillSwitchResponse,
  LoginResponse,
  OutcomeInput,
  OutcomeRecord,
  PriceQuote,
  Role,
  Scorecard,
  WeekHistory,
  StoreContact,
  Suggestion,
} from "./types";

/** `status` is the HTTP code: 401 sign in again, 423 switched off, 429 too many PIN tries. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = loadSession()?.token;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    // A 401 on login just means a wrong PIN; anywhere else it means the sign-in ended.
    if (response.status === 401 && token) signalExpired();
    if (response.status === 423) signalSwitchedOff();
    throw new ApiError(response.status, `${response.status} ${path}`);
  }
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
  login: async (pin: string) => {
    const session = await request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ pin }),
    });
    saveSession(session);
    return session;
  },
  orgChart: () => request<OrgChart>("/auth/org"),
  logout: () => clearSession(),
  suggestions: (params: { role?: Role; store_id?: string; kind?: string; state?: string }) =>
    request<Suggestion[]>(`/suggestions${query(params)}`),
  decide: (
    role: Role,
    suggestionId: string,
    body: { action: Approval["action"]; edited_units?: number; reason?: string },
  ) => {
    // The server fills in who and when from the sign-in; the contract still needs the fields.
    const approval: Approval = {
      suggestion_id: suggestionId,
      actor_role: role,
      actor_id: loadSession()?.actor_id ?? "",
      at: new Date().toISOString(),
      ...body,
    };
    return request<Suggestion>(`/suggestions/${encodeURIComponent(suggestionId)}/decision`, {
      method: "POST",
      body: JSON.stringify(approval),
    });
  },
  dcOrders: () => request<DcOrders>("/dc/orders"),
  dcTotals: () => request<DcTotals>("/dc/totals"),
  prices: () => request<PriceQuote[]>("/prices"),
  farmers: () => request<FarmerVolumeForecast[]>("/farmers/forecast"),
  scorecard: () => request<Scorecard[]>("/scorecard"),
  weekHistory: () => request<WeekHistory>("/history/week"),
  dayHistory: (date: string) => request<DayView>(`/history/day${query({ date })}`),
  historySeries: (period: "week" | "month", storeId?: string) =>
    request<HistorySeries>(`/history/series${query({ period, store_id: storeId })}`),
  farmerDay: (date: string) => request<FarmerDay>(`/farmers/day${query({ date })}`),
  contacts: () => request<StoreContact[]>("/contacts"),
  recordedScorecard: () => request<Scorecard[]>("/scorecard/recorded"),
  recordOutcome: (body: OutcomeInput) =>
    request<OutcomeRecord>("/outcomes", { method: "POST", body: JSON.stringify(body) }),
  setKillSwitch: (on: boolean) =>
    request<KillSwitchResponse>("/admin/kill-switch", {
      method: "POST",
      body: JSON.stringify({ on }),
    }),
  ask: (suggestionId: string, question: string) =>
    request<AskResponse>("/assistant/ask", {
      method: "POST",
      body: JSON.stringify({ suggestion_id: suggestionId, question }),
    }),
};
