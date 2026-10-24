import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { stubApi } from "../testing";
import { Instructions } from "./Instructions";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions and the policy wording, read only", async () => {
  stubApi({
    "GET /api/instructions": { instructions: "Decide each claim." },
    "GET /api/policy-wording": { version: "2026.1", text: "Section 3." },
  });
  render(<Instructions />);
  expect(await screen.findByText("Decide each claim.")).toBeDefined();
  expect(await screen.findByText("Section 3.")).toBeDefined();
  expect(screen.getByText("version 2026.1")).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows when the instructions can't be loaded", async () => {
  stubApi({});
  render(<Instructions />);
  expect(
    await screen.findByText(/The instructions could not be loaded/),
  ).toBeDefined();
});
