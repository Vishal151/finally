import { test, expect } from "@playwright/test";

test.describe("Watchlist CRUD", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });
  });

  test("add a ticker to the watchlist", async ({ page }) => {
    const tickerInput = page.getByPlaceholder("Add ticker...");
    const addButton = page.getByRole("button", { name: "Add" });

    await tickerInput.fill("PYPL");
    await addButton.click();

    await expect(page.getByText("PYPL", { exact: true })).toBeVisible({ timeout: 5000 });
  });

  test("remove a ticker from the watchlist", async ({ page }) => {
    await page.request.post("/api/watchlist", {
      data: { ticker: "PYPL" },
    });
    await page.reload();
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });

    await expect(page.getByText("PYPL", { exact: true })).toBeVisible({ timeout: 5000 });

    const pyplRow = page.locator("tr", {
      has: page.getByText("PYPL", { exact: true }),
    });
    await pyplRow.getByTitle("Remove").click();

    await expect(page.getByText("PYPL", { exact: true })).not.toBeVisible({ timeout: 5000 });
  });
});
