import { expect, test } from "@playwright/test";

const STATES = ["waiting", "in_progress", "awaiting_sign_off", "decided"];

test("the queue lists every claim with where it stands", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);

  let total = 0;
  for (const state of STATES) {
    total += Number(
      await page.getByTestId(`count-${state}`).locator(".count").textContent(),
    );
  }
  expect(total).toBe(25);

  const last = page.getByRole("row").filter({ hasText: "CLM-1025" });
  await expect(last.getByText("Waiting")).toBeVisible();
  await expect(page.getByRole("link", { name: "CLM-1001" })).toHaveAttribute(
    "href",
    "#/claims/CLM-1001",
  );
});
