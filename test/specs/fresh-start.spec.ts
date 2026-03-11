import { test, expect } from "@playwright/test";

const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
  "NVDA", "META", "JPM", "V", "NFLX",
];

test.describe("Fresh start", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the app to render (SSE keeps connection open so networkidle never fires)
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });
  });

  test("displays default watchlist with 10 tickers", async ({ page }) => {
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByText(ticker, { exact: true }).first()).toBeVisible();
    }
  });

  test("shows cash balance in header", async ({ page }) => {
    await expect(page.getByText(/Cash\$/)).toBeVisible();
  });

  test("prices are streaming via SSE", async ({ page }) => {
    await expect(async () => {
      const cells = page.locator("td.tabular-nums");
      const count = await cells.count();
      expect(count).toBeGreaterThan(0);
      const text = await cells.first().textContent();
      expect(text).not.toBe("--");
    }).toPass({ timeout: 10_000 });
  });

  test("shows connection status indicator", async ({ page }) => {
    await expect(page.getByText("Live")).toBeVisible({ timeout: 10_000 });
  });

  test("health endpoint responds", async ({ page }) => {
    const response = await page.request.get("/api/health");
    expect(response.status()).toBe(200);
  });
});
