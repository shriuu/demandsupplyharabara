import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("store manager: answers tonight's orders one at a time, then sees morning alerts and surplus", async ({ page }) => {
  await page.getByRole("button", { name: "Store manager" }).click();
  await expect(page.getByRole("heading", { name: "Tomato" })).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByRole("heading", { name: "Banana" })).toBeVisible();
  // edit with a reason
  await page.getByRole("button", { name: "More" }).click();
  await page.getByPlaceholder("Write a reason to save").fill("Festival crowd");
  await page.getByRole("button", { name: "Save change" }).click();
  await expect(page.getByRole("heading", { name: "Spinach" })).toBeVisible();
  await page.getByRole("button", { name: "Reject" }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByText("All orders answered")).toBeVisible();

  await page.getByRole("button", { name: "Morning alerts" }).click();
  await expect(page.locator('[data-light="red"]').first()).toBeVisible();
  await expect(page.locator('[data-light="amber"]').first()).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).first().click();

  await page.getByRole("button", { name: "Surplus plan" }).click();
  await expect(page.getByText(/Pickup 17:00/)).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByText("Nothing to do")).toBeVisible();
});

test("area manager: scoreboard shows all three, kill switch asks first", async ({ page }) => {
  await page.getByRole("button", { name: "Area manager" }).click();
  await expect(page.getByLabel("Wasted")).toBeVisible();
  await expect(page.getByLabel("Empty shelves")).toBeVisible();
  await expect(page.getByLabel("Farmer share")).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).first().click();
  await page.getByRole("button", { name: /Stop all suggestions/ }).click();
  await page.getByRole("button", { name: "No, go back" }).click();
  await expect(page.getByText("Suggestions are stopped")).toHaveCount(0);
  await page.getByRole("button", { name: /Stop all suggestions/ }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByText("Suggestions are stopped")).toBeVisible();
});

test("dc lead: totals, price warnings with citation, trimming suggestion", async ({ page }) => {
  await page.getByRole("button", { name: "DC buying lead" }).click();
  await expect(page.getByText("Price unavailable")).toBeVisible();
  await expect(page.getByText(/Mock price feed/).first()).toBeVisible();
  await expect(page.getByText("Buy 6 less at the mandi")).toBeVisible();
});

test("farmer coordinator: volumes are labelled estimate", async ({ page }) => {
  await page.getByRole("button", { name: "Farmer group" }).click();
  await expect(page.getByText("Estimate", { exact: true })).toHaveCount(2);
});

test("chat panel works on a screen", async ({ page }) => {
  await page.getByRole("button", { name: "Store manager" }).click();
  await page.getByRole("button", { name: "Ask" }).click();
  await page.getByPlaceholder("Type your question").fill("why?");
  await page.keyboard.press("Enter");
  await expect(page.locator(".chat-a")).toContainText("Rain is coming tomorrow");
});
