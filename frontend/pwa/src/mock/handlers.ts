// An in-memory stand-in for the API, typed from the generated OpenAPI types so a shape that
// drifts from the server fails the typecheck. Used by the dev server (VITE_MOCK_API) and tests.
import type {
  Approval,
  AskResponse,
  Health,
  KillSwitchResponse,
  LoginResponse,
  OutcomeInput,
  OutcomeRecord,
  Role,
  Suggestion,
} from "../api/types";
import { dcTotals, farmerForecast, prices, scorecards, suggestions } from "./fixtures";

export interface MockResponse {
  status: number;
  body: unknown;
}

/** Synthetic sign-ins for the mock only. */
export const MOCK_PINS: Record<string, Omit<LoginResponse, "token">> = {
  "1111": { role: "store_manager", actor_id: "mock-store", store_id: "S01" },
  "3333": { role: "area_manager", actor_id: "mock-area", store_id: null },
  "4444": { role: "dc_lead", actor_id: "mock-dc", store_id: null },
  "5555": { role: "farmer_coordinator", actor_id: "mock-farmer", store_id: null },
};

const MAX_FAILED_PINS = 5;

export function createMockApi() {
  let items: Suggestion[] = suggestions();
  let killSwitch = false;
  let failedPins = 0;
  const tokens = new Map<string, Omit<LoginResponse, "token">>();
  const asked: { suggestion_id: string; question: string }[] = [];
  const decisions: Approval[] = [];
  const outcomes: OutcomeRecord[] = [];

  function handle(method: string, url: string, rawBody?: string, authorization?: string): MockResponse {
    const parsed = new URL(url, "http://mock");
    const path = parsed.pathname.replace(/^\/api\/v1/, "");
    const q = parsed.searchParams;
    const json = (body: unknown, status = 200): MockResponse => ({ status, body });
    const detail = (status: number, text: string) => json({ detail: text }, status);

    if (method === "GET" && path === "/health") {
      return json({ status: "ok", kill_switch: killSwitch } satisfies Health);
    }
    if (method === "POST" && path === "/auth/login") {
      if (failedPins >= MAX_FAILED_PINS) return detail(429, "too many attempts");
      const { pin } = JSON.parse(rawBody ?? "{}") as { pin: string };
      const user = MOCK_PINS[pin];
      if (!user) {
        failedPins += 1;
        return detail(401, "wrong PIN");
      }
      const token = `mock-token-${tokens.size + 1}`;
      tokens.set(token, user);
      return json({ token, ...user } satisfies LoginResponse);
    }

    const user = tokens.get((authorization ?? "").replace(/^Bearer /, ""));
    if (!user) return detail(401, "sign in first");
    const need = (...roles: Role[]) => (roles.includes(user.role) ? null : detail(403, "wrong role"));

    if (method === "POST" && path === "/admin/kill-switch") {
      const denied = need("area_manager");
      if (denied) return denied;
      killSwitch = (JSON.parse(rawBody ?? "{}") as { on: boolean }).on;
      return json({ status: "ok", kill_switch: killSwitch } satisfies KillSwitchResponse);
    }
    if (method === "GET" && path === "/suggestions") {
      if (killSwitch) return json([]);
      const role = q.get("role");
      const out = items.filter(
        (s) =>
          (user.role !== "store_manager" || s.store_id === user.store_id) &&
          (!role || s.approver_role === role) &&
          (!q.get("store_id") || s.store_id === q.get("store_id")) &&
          (!q.get("kind") || s.payload.kind === q.get("kind")) &&
          (!q.get("state") || s.state === q.get("state")),
      );
      return json(out);
    }
    const decision = path.match(/^\/suggestions\/([^/]+)\/decision$/);
    if (method === "POST" && decision) {
      if (killSwitch) return detail(423, "suggestions are switched off");
      const approval = JSON.parse(rawBody ?? "{}") as Approval;
      const found = items.find((s) => s.id === decodeURIComponent(decision[1]));
      if (!found) return detail(404, "no such suggestion");
      if (found.approver_role !== user.role || approval.actor_role !== user.role) return detail(403, "not your decision");
      if (approval.action === "edit" && (approval.edited_units == null || !approval.reason)) {
        return detail(422, "an edit needs units and a reason");
      }
      decisions.push(approval);
      const state = { approve: "approved", edit: "edited", reject: "rejected" }[approval.action] as Suggestion["state"];
      const updated = { ...found, state };
      items = items.map((s) => (s.id === found.id ? updated : s));
      return json(updated);
    }
    if (method === "POST" && path === "/outcomes") {
      const body = JSON.parse(rawBody ?? "{}") as OutcomeInput;
      const denied = need(body.kind === "closing" ? "store_manager" : "dc_lead");
      if (denied) return denied;
      if (body.kind === "closing" && body.store_id !== user.store_id) return detail(403, "not your store");
      const record: OutcomeRecord = { ...body, recorded_by: user.actor_id, recorded_at: new Date().toISOString() } as OutcomeRecord;
      outcomes.push(record);
      items = items.map((s) =>
        s.id === body.suggestion_id && (s.state === "approved" || s.state === "edited") ? { ...s, state: "done" } : s,
      );
      return json(record);
    }
    if (method === "GET" && path === "/dc/totals") return need("dc_lead") ?? json(dcTotals);
    if (method === "GET" && path === "/prices") return need("dc_lead") ?? json(prices);
    if (method === "GET" && path === "/farmers/forecast") return need("farmer_coordinator") ?? json(farmerForecast);
    if (method === "GET" && path === "/contacts") {
      // test numbers only: the real file ships empty
      const rows = [
        { store_id: "S01", name: "Test manager", phone: "+91 90000 00001" },
        { store_id: "S02", name: null, phone: null },
      ];
      return need("area_manager") ?? json(rows);
    }
    if (method === "GET" && path === "/scorecard/recorded") return need("area_manager") ?? json([]);
    if (method === "GET" && path === "/scorecard") return need("area_manager") ?? json(scorecards);
    if (method === "POST" && path === "/assistant/ask") {
      const body = JSON.parse(rawBody ?? "{}") as { suggestion_id: string; question: string };
      asked.push(body);
      const found = items.find((s) => s.id === body.suggestion_id);
      if (!found) return detail(404, "no such suggestion");
      const answer = /why|reason|because/i.test(body.question) ? found.reason : "I don't have that.";
      return json({ suggestion_id: found.id, answer, source: "assistant" } satisfies AskResponse);
    }
    return detail(404, "not found");
  }

  return { handle, asked, decisions, outcomes };
}

/** Replace window.fetch with the mock (browser or jsdom). Returns the mock for assertions. */
export function installMockFetch() {
  const mock = createMockApi();
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const headers = new Headers(init?.headers);
    const { status, body } = mock.handle(
      init?.method ?? "GET",
      url,
      init?.body as string | undefined,
      headers.get("Authorization") ?? undefined,
    );
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return mock;
}
