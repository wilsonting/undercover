import { vi } from "vitest";
import type { Claim, ClaimSummary } from "./api";

/** Stub fetch with replies by "METHOD path". A function reply sees the request body. */
export function stubApi(routes: Record<string, unknown>) {
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(
        Response.json({ detail: `No route ${key}` }, { status: 404 }),
      );
    }
    const route = routes[key];
    const body: unknown = init?.body
      ? JSON.parse(init.body as string)
      : undefined;
    const reply =
      typeof route === "function"
        ? (route as (body: unknown) => unknown)(body)
        : route;
    if (reply instanceof Response) return Promise.resolve(reply);
    return Promise.resolve(Response.json(reply));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

export function summary(overrides: Partial<ClaimSummary> = {}): ClaimSummary {
  return {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    amount_claimed: 420,
    submitted_on: "2026-06-24",
    status: "waiting",
    decision: null,
    payout: null,
    ...overrides,
  };
}

export function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled by the airline",
    story: "My flight home from Rome was canceled.",
    items: [
      {
        description: "Airport hotel, one night",
        category: "accommodation",
        amount: 245,
      },
    ],
    amount_claimed: 245,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "One night, $245.00.",
      },
    ],
    status: "waiting",
    thread_id: null,
    decision: null,
    decided_at: null,
    needs_sign_off: false,
    sign_off: null,
    payment: null,
    ...overrides,
  };
}
