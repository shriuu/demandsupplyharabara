// An in-memory stand-in for the API. Used by the dev server (VITE_MOCK_API) and by tests.
import type { Approval, Health, Suggestion } from "../api/types";
import { dcTotals, farmerForecast, prices, scorecards, suggestions } from "./fixtures";

export interface MockResponse {
  status: number;
  body: unknown;
}

export function createMockApi() {
  let items: Suggestion[] = suggestions();
  let killSwitch = false;
  const asked: { suggestion_id: string; question: string }[] = [];
  const decisions: Approval[] = [];

  function handle(method: string, url: string, rawBody?: string): MockResponse {
    const parsed = new URL(url, "http://mock");
    const path = parsed.pathname.replace(/^\/api\/v1/, "");
    const q = parsed.searchParams;
    const json = (body: unknown, status = 200): MockResponse => ({ status, body });

    if (method === "GET" && path === "/health") {
      return json({ status: "ok", kill_switch: killSwitch } satisfies Health);
    }
    if (method === "POST" && path === "/admin/kill-switch") {
      killSwitch = true;
      return json({ status: "ok", kill_switch: true } satisfies Health);
    }
    if (method === "GET" && path === "/suggestions") {
      if (killSwitch) return json([]);
      const role = q.get("role");
      const out = items.filter(
        (s) =>
          (!role || s.approver_role === role) &&
          (!q.get("store_id") || s.store_id === q.get("store_id")) &&
          (!q.get("kind") || s.payload.kind === q.get("kind")) &&
          (!q.get("state") || s.state === q.get("state")),
      );
      return json(out);
    }
    const decision = path.match(/^\/suggestions\/([^/]+)\/decision$/);
    if (method === "POST" && decision) {
      const approval = JSON.parse(rawBody ?? "{}") as Approval;
      const found = items.find((s) => s.id === decodeURIComponent(decision[1]));
      if (!found) return json({ detail: "unknown" }, 404);
      if (approval.action === "edit" && (approval.edited_units == null || !approval.reason)) {
        return json({ detail: "an edit needs units and a reason" }, 422);
      }
      decisions.push(approval);
      const state = { approve: "approved", edit: "edited", reject: "rejected" }[approval.action] as Suggestion["state"];
      const updated = { ...found, state };
      items = items.map((s) => (s.id === found.id ? updated : s));
      return json(updated);
    }
    if (method === "GET" && path === "/dc/totals") return json(dcTotals);
    if (method === "GET" && path === "/prices") return json(prices);
    if (method === "GET" && path === "/farmers/forecast") return json(farmerForecast);
    if (method === "GET" && path === "/scorecard") return json(scorecards);
    if (method === "POST" && path === "/assistant/ask") {
      const body = JSON.parse(rawBody ?? "{}") as { suggestion_id: string; question: string };
      asked.push(body);
      const found = items.find((s) => s.id === body.suggestion_id);
      if (!found || !/why|reason|because/i.test(body.question)) return json({ answer: null });
      return json({ answer: found.reason });
    }
    return json({ detail: "not found" }, 404);
  }

  return { handle, asked, decisions };
}

/** Replace window.fetch with the mock (browser or jsdom). Returns the mock for assertions. */
export function installMockFetch() {
  const mock = createMockApi();
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const { status, body } = mock.handle(init?.method ?? "GET", url, init?.body as string | undefined);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return mock;
}
