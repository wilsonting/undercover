import { expect, test, type APIRequestContext } from "@playwright/test";

const decision = (payout: number) => ({
  decision: "approve",
  payout,
  calculation: `Covered costs: $${payout.toFixed(2)}`,
  reason: "The documents support the claim. The costs are covered.",
  policy_section: "Section 3, Trip Delay",
});

async function start(request: APIRequestContext, claimId: string) {
  const response = await request.post(`/api/claims/${claimId}/start`, {
    data: { thread_id: `e2e-${claimId}` },
  });
  expect(response.ok()).toBe(true);
}

async function addStep(
  request: APIRequestContext,
  claimId: string,
  content: string,
) {
  await request.post(`/api/claims/${claimId}/steps`, {
    data: { thread_id: `e2e-${claimId}`, kind: "thinking", content },
  });
}

test("the claim page follows the agent as it works", async ({
  page,
  request,
}) => {
  await start(request, "CLM-1002");
  await addStep(request, "CLM-1002", "Reading the claim.");
  await addStep(request, "CLM-1002", "Checking the policy.");
  await page.goto("/#/claims/CLM-1002");
  await expect(page.locator(".status")).toHaveText("In progress");
  await expect(page.getByText("Reading the claim.")).toBeVisible();
  await expect(page.getByText("Checking the policy.")).toBeVisible();
  await addStep(request, "CLM-1002", "The theft is covered.");
  await expect(page.getByText("The theft is covered.")).toBeVisible();
});

test("an approved claim shows its decision and payment", async ({
  page,
  request,
}) => {
  await start(request, "CLM-1003");
  await request.post("/api/claims/CLM-1003/decision", { data: decision(420) });
  await request.post("/api/claims/CLM-1003/payment", { data: { amount: 420 } });
  await page.goto("/#/claims/CLM-1003");
  const panel = page.getByRole("region", { name: "Decision" });
  await expect(panel.getByText("Approved")).toBeVisible();
  await expect(panel.getByText(decision(420).reason)).toBeVisible();
  await expect(panel.getByText("Section 3, Trip Delay")).toBeVisible();
  await expect(panel.getByText("Paid $420.00")).toBeVisible();
});

test("a handler signs off a payout over $1,000", async ({ page, request }) => {
  await start(request, "CLM-1004");
  await request.post("/api/claims/CLM-1004/decision", { data: decision(1350) });
  const blocked = await request.post("/api/claims/CLM-1004/payment", {
    data: { amount: 1350 },
  });
  expect(blocked.status()).toBe(409);

  await page.goto("/#/claims/CLM-1004");
  await expect(page.locator(".status")).toHaveText("Waiting for sign-off");
  await page.getByLabel("Handler").selectOption({ label: "Priya Raman" });
  await page
    .getByRole("button", { name: "Sign off and pay $1,350.00" })
    .click();
  await expect(page.locator(".status")).toHaveText("Decided");
  await expect(page.getByText("Signed off by Priya Raman")).toBeVisible();
  await expect(page.getByText("Paid $1,350.00")).toBeVisible();

  await page.getByRole("link", { name: "Back to the queue" }).click();
  const row = page.getByRole("row").filter({ hasText: "CLM-1004" });
  await expect(row.getByText("Decided")).toBeVisible();
  await expect(row.getByText("$1,350.00").last()).toBeVisible();
});

test("the instructions page shows what the agent is told", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  await expect(
    page.getByText("How to work a claim", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("How we work out your payment", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("the queue opens a claim", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page.getByRole("heading", { name: "CLM-1001" })).toBeVisible();
  await expect(page.getByText("Maya Patel").first()).toBeVisible();
});
