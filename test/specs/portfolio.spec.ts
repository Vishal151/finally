import { test, expect } from "@playwright/test";

test.describe("Portfolio", () => {
  test("portfolio API returns correct structure", async ({ page }) => {
    const response = await page.request.get("/api/portfolio");
    expect(response.status()).toBe(200);
    const data = await response.json();

    expect(data).toHaveProperty("cash_balance");
    expect(data).toHaveProperty("total_value");
    expect(data).toHaveProperty("positions");
    expect(typeof data.cash_balance).toBe("number");
    expect(data.cash_balance).toBeGreaterThan(0);
    expect(Array.isArray(data.positions)).toBe(true);
  });

  test("portfolio history returns snapshots after trade", async ({ page }) => {
    await page.request.post("/api/portfolio/trade", {
      data: { ticker: "V", quantity: 2, side: "buy" },
    });

    const history = await page.request.get("/api/portfolio/history");
    expect(history.status()).toBe(200);
    const data = await history.json();
    expect(data.snapshots).toBeTruthy();
    expect(data.snapshots.length).toBeGreaterThan(0);
  });

  test("positions table shows bought positions on page", async ({ page }) => {
    await page.request.post("/api/portfolio/trade", {
      data: { ticker: "GOOGL", quantity: 5, side: "buy" },
    });

    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });

    await expect(page.getByText("GOOGL").first()).toBeVisible();
  });

  test("heatmap or portfolio visualization renders", async ({ page }) => {
    await page.request.post("/api/portfolio/trade", {
      data: { ticker: "TSLA", quantity: 3, side: "buy" },
    });

    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });
    // Wait for portfolio data to load and heatmap to render
    await page.waitForTimeout(2000);

    // Heatmap renders colored divs with ticker names inside them
    // When there are positions, the "No positions" text disappears
    const heatmapTicker = page.locator(".font-bold.text-white.text-xs");
    const count = await heatmapTicker.count();
    expect(count).toBeGreaterThan(0);
  });
});
