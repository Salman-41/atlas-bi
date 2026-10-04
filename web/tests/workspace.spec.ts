import { test, expect } from "@playwright/test";
test("demonstration dates, reports, theme and scenario remain honest", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore demonstration" }).click();
  await expect(
    page.getByText("SYNTHETIC DEMONSTRATION — all figures are illustrative."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await expect(page.locator(".workspace")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await expect(page.locator(".workspace")).not.toHaveClass(/dark/);
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.getByLabel("Start date").fill("2019-10-20");
  await page.getByLabel("End date").fill("2019-10-10");
  await expect(page.locator('.error[role="alert"]')).toContainText(
    "Start date",
  );
  await page.getByLabel("End date").fill("2019-10-31");
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toBe("atlas-report.csv");
  await page.getByRole("button", { name: "Export PDF" }).click();
  await expect(page.locator('.error[role="alert"]')).toContainText(
    "requires the connected",
  );
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await page.getByLabel("Assumed available stock").fill("0");
  await expect(page.getByText("126 units", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ask Atlas", exact: true }).click();
  await page.getByLabel("Your question").fill("What does the forecast show?");
  await page.getByRole("button", { name: "Explore question" }).click();
  await expect(page.getByRole("status")).toContainText("No model is trained");
});
test("login exposes API errors without persisting credentials", async ({
  page,
}) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({ status: 401, body: "{}" }),
  );
  await page.goto("/");
  await page.getByLabel("Username").fill("test");
  await page.getByLabel("Password").fill("invalid");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator('.error[role="alert"]')).toContainText(
    "Sign-in failed",
  );
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});

test("missing warehouse offers setup and an explicit demonstration", async ({
  page,
}) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({ json: { access_token: "test-token" } }),
  );
  await page.route("**/api/overview?**", (route) =>
    route.fulfill({
      status: 503,
      json: {
        code: "warehouse_missing",
        detail: "Your analytics dataset has not been loaded yet.",
      },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Your workspace is ready. Add your data.",
    }),
  ).toBeVisible();
  await page.getByText("Show dataset setup commands").click();
  await expect(
    page.getByText("python scripts/acquire.py", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Explore demonstration" }).click();
  await expect(
    page.getByRole("heading", { name: "Business at a glance" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Your workspace is ready. Add your data.",
    }),
  ).not.toBeVisible();
});

test("trend supports weekly and cumulative analysis", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore demonstration" }).click();
  await page.getByRole("button", { name: "Weekly", exact: true }).click();
  await expect(
    page.getByRole("img", { name: /Purchase value chart: weekly/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cumulative", exact: true }).click();
  await expect(
    page.getByRole("img", { name: /Purchase value chart: cumulative/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Data Explorer", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Go deeper with the real dataset" }),
  ).toBeVisible();
});
