import { expect, test, type Page } from "@playwright/test";

async function pin(page: Page, digits: string) {
  for (const d of digits) await page.getByRole("button", { name: d, exact: true }).click();
  await page.getByRole("button", { name: "Go" }).click();
}

test("store manager signs in with a PIN, accepts an order, and the server records it", async ({ page }) => {
  await page.goto("/");
  await pin(page, "0000");
  await expect(page.getByText("Wrong PIN. Try again.")).toBeVisible();

  await pin(page, "1111");
  await expect(page.getByRole("heading", { name: "Tomato" })).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByRole("heading", { name: "Banana" })).toBeVisible();

  // The approval is stored: ask the real API with the session's own token.
  const state = await page.evaluate(async () => {
    const { token } = JSON.parse(sessionStorage.getItem("harabhara.session") ?? "{}");
    const r = await fetch("/api/v1/suggestions/e2e-tomato", { headers: { Authorization: `Bearer ${token}` } });
    return ((await r.json()) as { state: string }).state;
  });
  expect(state).toBe("approved");

  // A reload keeps the sign-in and the answered order stays answered.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Banana" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tomato" })).toHaveCount(0);
});

test("the area manager can switch suggestions off and on", async ({ page }) => {
  await page.goto("/");
  await pin(page, "3333");
  await page.getByRole("button", { name: /Stop all suggestions/ }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByRole("button", { name: /Start suggestions again/ })).toBeVisible();
  await page.getByRole("button", { name: /Start suggestions again/ }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect(page.getByRole("button", { name: /Stop all suggestions/ })).toBeVisible();
});
