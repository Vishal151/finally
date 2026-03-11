import { test, expect } from "@playwright/test";

test.describe("SSE streaming", () => {
  test("SSE endpoint streams price data", async ({ page }) => {
    await page.goto("/");

    // Use page.evaluate to connect to SSE and collect events
    const events = await page.evaluate(
      () =>
        new Promise<string[]>((resolve) => {
          const es = new EventSource("/api/stream/prices");
          const collected: string[] = [];

          es.onmessage = (event) => {
            collected.push(event.data);
            if (collected.length >= 3) {
              es.close();
              resolve(collected);
            }
          };

          es.onerror = () => {
            es.close();
            resolve(collected);
          };

          setTimeout(() => {
            es.close();
            resolve(collected);
          }, 10_000);
        })
    );

    expect(events.length).toBeGreaterThan(0);

    // Each event should be valid JSON with ticker, price, timestamp
    const parsed = JSON.parse(events[0]);
    expect(parsed).toHaveProperty("ticker");
    expect(parsed).toHaveProperty("price");
    expect(parsed).toHaveProperty("timestamp");
    expect(typeof parsed.price).toBe("number");
    expect(parsed.price).toBeGreaterThan(0);
  });

  test("SSE delivers updates for default watchlist tickers", async ({ page }) => {
    await page.goto("/");

    const events = await page.evaluate(
      () =>
        new Promise<string[]>((resolve) => {
          const es = new EventSource("/api/stream/prices");
          const collected: string[] = [];

          es.onmessage = (event) => {
            collected.push(event.data);
            if (collected.length >= 20) {
              es.close();
              resolve(collected);
            }
          };

          setTimeout(() => {
            es.close();
            resolve(collected);
          }, 15_000);
        })
    );

    // Should have received updates for multiple tickers
    const tickers = new Set(events.map((e) => JSON.parse(e).ticker));
    expect(tickers.size).toBeGreaterThan(1);
  });
});
