import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { stubApi, summary } from "../testing";
import { Queue } from "./Queue";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const claims = [
  summary(),
  summary({ claim_id: "CLM-1002", status: "in_progress" }),
  summary({
    claim_id: "CLM-1003",
    status: "awaiting_sign_off",
    decision: "approve",
    payout: 1350,
  }),
  summary({
    claim_id: "CLM-1004",
    status: "decided",
    decision: "decline",
    payout: 0,
  }),
];

it("counts the claims in each state", async () => {
  stubApi({ "GET /api/claims": claims });
  render(<Queue />);
  await screen.findByText("CLM-1001");
  for (const status of [
    "waiting",
    "in_progress",
    "awaiting_sign_off",
    "decided",
  ]) {
    expect(
      within(screen.getByTestId(`count-${status}`)).getByText("1"),
    ).toBeDefined();
  }
});

it("lists each claim with a link, its status and its decision", async () => {
  stubApi({ "GET /api/claims": claims });
  render(<Queue />);
  const link = await screen.findByRole("link", { name: "CLM-1003" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1003");
  const row = link.closest("tr");
  if (!row) throw new Error("No row for CLM-1003");
  expect(within(row).getByText("Waiting for sign-off")).toBeDefined();
  expect(within(row).getByText("Approved")).toBeDefined();
  expect(within(row).getByText("$1,350.00")).toBeDefined();
  expect(within(row).getByText("Trip delay")).toBeDefined();
  expect(screen.getByText("Declined")).toBeDefined();
});

it("starts the agent on the queue", async () => {
  const fetch = stubApi({
    "GET /api/claims": claims,
    "POST /api/queue/run": ["CLM-1001"],
  });
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Work the queue" }),
  );
  expect(
    await screen.findByText(
      "The agent is working through 1 claim, one at a time.",
    ),
  ).toBeDefined();
  expect(fetch).toHaveBeenCalledWith(
    "/api/queue/run",
    expect.objectContaining({ method: "POST" }),
  );
});

it("says why the queue could not be started", async () => {
  stubApi({
    "GET /api/claims": claims,
    "POST /api/queue/run": new Response(JSON.stringify({ detail: "Busy" }), {
      status: 409,
    }),
  });
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Work the queue" }),
  );
  expect(await screen.findByText("Busy")).toBeDefined();
});

it("can't work a queue with nothing waiting", async () => {
  stubApi({ "GET /api/claims": [summary({ status: "decided" })] });
  render(<Queue />);
  const button = await screen.findByRole("button", { name: "Work the queue" });
  expect(button.hasAttribute("disabled")).toBe(true);
});

it("shows an empty queue", async () => {
  stubApi({ "GET /api/claims": [] });
  render(<Queue />);
  expect(await screen.findByText("The queue is empty.")).toBeDefined();
});

it("shows when the queue can't be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Queue />);
  expect(
    await screen.findByText("The queue could not be loaded: offline"),
  ).toBeDefined();
});

it("refreshes the queue", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetch = stubApi({ "GET /api/claims": claims });
  render(<Queue />);
  await screen.findByText("CLM-1001");
  await vi.advanceTimersByTimeAsync(2000);
  await waitFor(() => {
    expect(fetch.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
