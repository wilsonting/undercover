import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim, Step } from "../api";
import { claim, stubApi } from "../testing";
import { ClaimPage } from "./Claim";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const policy = {
  policy_id: "POL-2001",
  plan: { name: "UnderCover Premium" },
  add_ons: [{ add_on: "electronics_plus", name: "Electronics Plus" }],
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
  },
  travelers: ["Maya Patel"],
};

const handlers = [
  { handler_id: "HND-01", name: "Dana Whitfield", role: "Senior" },
  { handler_id: "HND-03", name: "Priya Raman", role: "Handler" },
];

const approved = {
  decision: "approve" as const,
  payout: 1350,
  calculation: "Laptop $1,200.00 + bag $150.00",
  reason: "The bag was stolen from the hotel room. The police report backs it.",
  policy_section: "Section 5, Baggage and Personal Effects",
};

function step(id: number, kind: Step["kind"], content: string): Step {
  return {
    step_id: id,
    thread_id: "t-1",
    kind,
    content,
    created_at: "2026-10-24T10:00:00+00:00",
  };
}

function routes(current: Claim, steps: Step[] = []) {
  return {
    "GET /api/claims/CLM-1001": current,
    "GET /api/claims/CLM-1001/steps": steps,
    "GET /api/policies/POL-2001": policy,
    "GET /api/handlers": handlers,
  };
}

it("shows the claim in full", async () => {
  stubApi(routes(claim()));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel, one night")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText(/UnderCover Premium/)).toBeDefined();
  expect(screen.getByText(/Electronics Plus/)).toBeDefined();
  expect(screen.getByText("No decision yet.")).toBeDefined();
  expect(
    screen.getByText("The agent hasn't worked on this claim yet."),
  ).toBeDefined();
});

it("runs the agent on a waiting claim", async () => {
  const fetch = stubApi({
    ...routes(claim()),
    "POST /api/claims/CLM-1001/run": claim(),
  });
  render(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  await waitFor(() => {
    expect(fetch).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/run",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

it("says why the agent could not start", async () => {
  stubApi({
    ...routes(claim()),
    "POST /api/claims/CLM-1001/run": Response.json(
      { detail: "Claim CLM-1001 is in progress, not waiting" },
      { status: 409 },
    ),
  });
  render(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(
    await screen.findByText("Claim CLM-1001 is in progress, not waiting"),
  ).toBeDefined();
});

it("follows the agent's steps while it works", async () => {
  const steps = [step(1, "tool_call", 'get_claim {"claim_id": "CLM-1001"}')];
  stubApi({
    ...routes(claim({ status: "in_progress" })),
    "GET /api/claims/CLM-1001/steps": () => steps,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText('get_claim {"claim_id": "CLM-1001"}'),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
  expect(screen.getByText("The agent is working on this claim.")).toBeDefined();
  steps.push(step(2, "tool_result", 'get_claim: {"story": "..."}'));
  steps.push(step(3, "thinking", "The delay is covered."));
  steps.push(step(4, "error", "The run stopped with an error: timeout"));
  expect(
    await screen.findByText("Reply from get_claim", {}, { timeout: 3000 }),
  ).toBeDefined();
  expect(screen.getByText("The delay is covered.")).toBeDefined();
  expect(
    screen.getByText("The run stopped with an error: timeout"),
  ).toBeDefined();
});

it.each([
  ["decline", "Declined"],
  ["refer", "Referred"],
] as const)("shows a %s decision with its reason", async (kind, label) => {
  stubApi(
    routes(
      claim({
        status: "decided",
        decision: { ...approved, decision: kind, payout: 0 },
      }),
    ),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText(label)).toBeDefined();
  expect(screen.getByText(approved.reason)).toBeDefined();
  expect(screen.getByText(approved.policy_section)).toBeDefined();
  expect(screen.queryByText(/with a payout of/)).toBeNull();
});

it("shows an approved claim that has been paid", async () => {
  stubApi(
    routes(
      claim({
        status: "decided",
        decision: { ...approved, payout: 420 },
        payment: { amount: 420, paid_at: "2026-10-24T10:00:00+00:00" },
      }),
    ),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Paid $420.00")).toBeDefined();
  expect(screen.getByText("Approved")).toBeDefined();
  expect(screen.getByText(approved.calculation)).toBeDefined();
});

it("shows an approved claim not paid yet", async () => {
  stubApi(
    routes(
      claim({ status: "decided", decision: { ...approved, payout: 420 } }),
    ),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
});

it("signs off a payout as the chosen handler", async () => {
  let current = claim({
    status: "awaiting_sign_off",
    decision: approved,
    needs_sign_off: true,
  });
  const signOffs: unknown[] = [];
  stubApi({
    ...routes(current),
    "GET /api/claims/CLM-1001": () => current,
    "POST /api/claims/CLM-1001/sign-off": (body: unknown) => {
      signOffs.push(body);
      current = {
        ...current,
        status: "decided",
        sign_off: {
          handler_id: "HND-03",
          handler_name: "Priya Raman",
          signed_off_at: "2026-10-24T10:00:00+00:00",
        },
        payment: { amount: 1350, paid_at: "2026-10-24T10:00:00+00:00" },
      };
      return current;
    },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off and pay $1,350.00",
  });
  expect(button.hasAttribute("disabled")).toBe(true);
  await screen.findByRole("option", { name: "Priya Raman" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-03" },
  });
  fireEvent.click(button);
  expect(await screen.findByText(/Signed off by Priya Raman/)).toBeDefined();
  expect(signOffs).toEqual([{ handler_id: "HND-03" }]);
  expect(screen.queryByRole("button", { name: /Sign off/ })).toBeNull();
});

it("says why a sign-off was refused", async () => {
  stubApi({
    ...routes(
      claim({
        status: "awaiting_sign_off",
        decision: approved,
        needs_sign_off: true,
      }),
    ),
    "POST /api/claims/CLM-1001/sign-off": Response.json(
      { detail: "No record HND-01" },
      { status: 404 },
    ),
  });
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Sign off/ }));
  const panel = screen.getByRole("region", { name: "Decision" });
  expect(await within(panel).findByText("No record HND-01")).toBeDefined();
});

it("shows when the claim can't be loaded", async () => {
  stubApi({});
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText(
      "Claim CLM-1001 could not be loaded: No route GET /api/claims/CLM-1001",
    ),
  ).toBeDefined();
});
