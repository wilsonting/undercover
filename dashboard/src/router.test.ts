import { expect, it } from "vitest";
import { money, words } from "./format";
import { parseRoute } from "./router";

it("reads the page from the address", () => {
  expect(parseRoute("")).toEqual({ page: "queue" });
  expect(parseRoute("#/")).toEqual({ page: "queue" });
  expect(parseRoute("#/claims/CLM-1001")).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
  expect(parseRoute("#/elsewhere")).toEqual({ page: "queue" });
});

it("formats money and labels", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(words("emergency_medical")).toBe("Emergency medical");
});
