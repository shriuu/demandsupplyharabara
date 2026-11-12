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
import { dayView, dcTotals, farmerDay, farmerForecast, historySeries, prices, scorecards, suggestions, weekHistory } from "./fixtures";
import { todayIso } from "../components/CalendarPick";

export interface MockResponse {
  status: number;
  body: unknown;
}

/** Synthetic sign-ins for the mock only. */
export const MOCK_PINS: Record<string, Omit<LoginResponse, "token">> = {
  "1111": { role: "store_manager", actor_id: "mock-store", store_id: "S01" },
  "3333": { role: "area_manager", actor_id: "mock-area", store_id: null },
  "6666": { role: "area_manager", actor_id: "mock-north", store_id: null, area_id: "north", area_name: "North" },
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
    if (method === "GET" && path === "/auth/org") {
      const place = (store_id: string, name: string) => ({ store_id, place: name });
      return json({
        areas: [
          {
            area_id: "south_central",
            name: "South and central",
            stores: [
              place("S01", "Jayanagar"),
              place("S02", "Indiranagar"),
              place("S03", "Koramangala"),
              place("S04", "HSR Layout"),
              place("S07", "Banashankari"),
              place("D02", "Electronic City"),
            ],
          },
          {
            area_id: "north",
            name: "North",
            stores: [place("S06", "Malleshwaram"), place("S08", "Yelahanka"), place("D03", "Hebbal")],
          },
          {
            area_id: "east",
            name: "East",
            stores: [place("S05", "Whitefield"), place("D01", "Bellandur"), place("D04", "Marathahalli")],
          },
        ],
      });
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
      const denied = need("area_manager") ?? (user.area_id ? detail(403, "all stores only") : null);
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
    if (method === "GET" && path === "/history/week") {
      const denied = need("store_manager", "area_manager");
      if (denied) return denied;
      return json(weekHistory(user.role === "store_manager" ? ["S01"] : ["S01", "S02"], user.role === "store_manager"));
    }
    if (method === "GET" && path === "/history/day") {
      const denied = need("store_manager");
      return denied ?? json(dayView(q.get("date") ?? todayIso(), todayIso(), true));
    }
    if (method === "GET" && path === "/history/series") {
      const denied = need("area_manager", "store_manager");
      if (denied) return denied;
      const series = historySeries(q.get("period") === "month" ? "month" : "week", todayIso(), user.role === "store_manager" ? "S01" : (q.get("store_id") ?? undefined));
      return json(user.role === "store_manager" ? { ...series, talk: [] } : series);
    }
    if (method === "GET" && path === "/farmers/day") {
      const denied = need("farmer_coordinator");
      return denied ?? json(farmerDay(q.get("date") ?? todayIso(), todayIso()));
    }
    if (method === "GET" && path === "/dc/orders") {
      const denied = need("dc_lead");
      if (denied) return denied;
      const orders = items.filter((s) => s.payload.kind === "order" && s.state !== "expired");
      const mockArea = (id: string) => (["S06", "S08", "D03"].includes(id) ? ["north", "North"] : ["S05", "D01", "D04"].includes(id) ? ["east", "East"] : ["south_central", "South and central"]);
      const lines = new Map<string, Map<string, { store_id: string; area_id: string; area_name: string; confirmed_units: number; waiting_units: number; rejected: boolean }>>();
      const bySku = new Map<string, { confirmed: number; waiting: number; decided: number; waitingN: number; rejected: number }>();
      for (const s of orders) {
        const units = (s.payload as { recommended_units: number }).recommended_units;
        const row = bySku.get(s.sku_id) ?? { confirmed: 0, waiting: 0, decided: 0, waitingN: 0, rejected: 0 };
        const [area_id, area_name] = mockArea(s.store_id);
        const perStore = lines.get(s.sku_id) ?? new Map();
        const line = perStore.get(s.store_id) ?? { store_id: s.store_id, area_id, area_name, confirmed_units: 0, waiting_units: 0, rejected: false };
        if (s.state === "proposed") { row.waiting += units; row.waitingN += 1; line.waiting_units += units; }
        else if (s.state === "rejected") { row.rejected += 1; line.rejected = true; }
        else { row.confirmed += units; row.decided += 1; line.confirmed_units += units; }
        perStore.set(s.store_id, line);
        lines.set(s.sku_id, perStore);
        bySku.set(s.sku_id, row);
      }
      const products = [...bySku.entries()].map(([sku_id, r]) => ({
        sku_id, confirmed_units: r.confirmed, waiting_units: r.waiting,
        stores_decided: r.decided, stores_waiting: r.waitingN, stores_rejected: r.rejected,
        stores: [...(lines.get(sku_id)?.values() ?? [])],
      }));
      const bought = outcomes
        .filter((o) => o.kind === "purchase" && o.units_bought)
        .map((o) => ({ sku_id: o.sku_id, source: o.source as "spot" | "farmer_group", market: o.market ?? null, units: o.units_bought as number }));
      return json({
        on: "2026-10-31", products, bought, markets: ["APMC Yeshwanthpur", "K.R. Market"],
        all_decided: products.every((p) => p.stores_waiting === 0), stale: false,
      });
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
    if (method === "GET" && path === "/scorecard") {
      return need("area_manager") ?? json(user.area_id ? scorecards.filter((c) => c.scope !== "chain") : scorecards);
    }
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

  /** Make every waiting order run out of time, as it does once the deadline passes. */
  const expireOrders = () => {
    items = items.map((s) => (s.payload.kind === "order" && s.state === "proposed" ? { ...s, state: "expired" } : s));
  };

  /** Make every waiting order answered, as if the manager had ticked them. */
  const answerOrders = () => {
    items = items.map((s) => (s.payload.kind === "order" && s.state === "proposed" ? { ...s, state: "approved" } : s));
  };

  /** Earlier days' approved orders for the same products, as a store has after a week of use. */
  const addOlderApproved = (days: number) => {
    const orders = items.filter((s) => s.payload.kind === "order");
    for (let d = 1; d <= days; d++) {
      for (const o of orders) {
        const at = new Date(new Date(o.created_at).getTime() - d * 86_400_000).toISOString();
        items.push({ ...o, id: `${o.id}-old${d}`, created_at: at, state: "approved" });
      }
    }
  };

  return { handle, asked, decisions, outcomes, expireOrders, answerOrders, addOlderApproved };
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
