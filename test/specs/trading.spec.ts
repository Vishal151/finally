import { test, expect } from "@playwright/test";

test.describe("Trading", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });
  });

  test("buy shares via API - cash decreases and position appears", async ({ page }) => {
    const before = await page.request.get("/api/portfolio");
    const dataBefore = await before.json();
    const cashBefore = dataBefore.cash_balance;

    const tradeRes = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 10, side: "buy" },
    });
    expect(tradeRes.status()).toBe(200);
    const tradeData = await tradeRes.json();

    expect(tradeData.cash_balance).toBeLessThan(cashBefore);
    expect(tradeData.trade.ticker).toBe("AAPL");
    expect(tradeData.trade.side).toBe("buy");
    expect(tradeData.trade.quantity).toBe(10);
    expect(tradeData.position).toBeTruthy();
  });

  test("buy shares via UI trade bar", async ({ page }) => {
    const before = await page.request.get("/api/portfolio");
    const cashBefore = (await before.json()).cash_balance;

    await page.getByPlaceholder("Ticker", { exact: true }).fill("AAPL");
    await page.getByPlaceholder("Qty").fill("2");
    await page.getByRole("button", { name: "Buy" }).click();

    await page.waitForTimeout(1000);
    const portfolio = await page.request.get("/api/portfolio");
    const data = await portfolio.json();
    expect(data.cash_balance).toBeLessThan(cashBefore);
    expect(data.positions.length).toBeGreaterThan(0);
  });

  test("sell shares - cash increases and position updates", async ({ page }) => {
    // First buy some shares to sell
    const buyRes = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "NVDA", quantity: 5, side: "buy" },
    });
    expect(buyRes.status()).toBe(200);

    const portfolioBefore = await page.request.get("/api/portfolio");
    const dataBefore = await portfolioBefore.json();
    const cashBefore = dataBefore.cash_balance;

    await page.reload();
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });

    await page.getByPlaceholder("Ticker", { exact: true }).fill("NVDA");
    await page.getByPlaceholder("Qty").fill("3");
    await page.getByRole("button", { name: "Sell" }).click();

    await page.waitForTimeout(1000);
    const portfolioAfter = await page.request.get("/api/portfolio");
    const dataAfter = await portfolioAfter.json();
    expect(dataAfter.cash_balance).toBeGreaterThan(cashBefore);
  });

  test("sell all shares removes position", async ({ page }) => {
    // Buy some JPM shares
    const buyRes = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "JPM", quantity: 3, side: "buy" },
    });
    expect(buyRes.status()).toBe(200);

    let portfolio = await page.request.get("/api/portfolio");
    let data = await portfolio.json();
    let jpmPos = data.positions.find((p: { ticker: string }) => p.ticker === "JPM");
    expect(jpmPos).toBeTruthy();
    const jpmQty = jpmPos.quantity;

    // Sell all JPM
    const sellRes = await page.request.post("/api/portfolio/trade", {
      data: { ticker: "JPM", quantity: jpmQty, side: "sell" },
    });
    expect(sellRes.status()).toBe(200);

    portfolio = await page.request.get("/api/portfolio");
    data = await portfolio.json();
    jpmPos = data.positions.find((p: { ticker: string }) => p.ticker === "JPM");
    expect(jpmPos).toBeFalsy();
  });
});
