import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("opens on the queue", async () => {
  stubApi({ "GET /api/claims": [summary()] });
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBe("page");
});

it("opens a claim and the instructions from the address", async () => {
  stubApi({
    "GET /api/claims/CLM-1001": claim(),
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": {
      policy_id: "POL-2001",
      plan: { name: "UnderCover Premium" },
      add_ons: [],
      trip: { destination: "Rome", departs_on: "a", returns_on: "b" },
      travelers: [],
    },
    "GET /api/instructions": { instructions: "Decide each claim." },
    "GET /api/policy-wording": { version: "2026.1", text: "Wording" },
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "CLM-1001" }),
  ).toBeDefined();
  window.location.hash = "#/instructions";
  window.dispatchEvent(new HashChangeEvent("hashchange"));
  expect(await screen.findByText("Decide each claim.")).toBeDefined();
});
