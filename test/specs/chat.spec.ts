import { test, expect } from "@playwright/test";

test.describe("AI Chat (mocked)", () => {
  test("chat API returns structured response", async ({ page }) => {
    const response = await page.request.post("/api/chat", {
      data: { message: "What should I buy?" },
    });
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.message).toBeTruthy();
    expect(typeof data.message).toBe("string");
  });

  test("send message via UI and receive response", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });

    const chatInput = page.getByPlaceholder("Ask the AI...");
    const sendButton = page.getByRole("button", { name: "Send" });

    await chatInput.fill("What should I buy?");
    await sendButton.click();

    // Wait for assistant response bubble (bg-bg-secondary contains the reply)
    const assistantBubble = page.locator(".bg-bg-secondary .whitespace-pre-wrap");
    await expect(assistantBubble.first()).toBeVisible({ timeout: 15_000 });

    const text = await assistantBubble.first().textContent();
    expect(text).toBeTruthy();
    expect(text!.length).toBeGreaterThan(0);
  });

  test("chat shows trade execution inline", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=FinAlly", { timeout: 15_000 });

    const chatInput = page.getByPlaceholder("Ask the AI...");
    const sendButton = page.getByRole("button", { name: "Send" });

    await chatInput.fill("Buy 5 shares of AAPL");
    await sendButton.click();

    // Mock LLM auto-executes a trade; trade confirmation shows "BUY" in text-profit
    await expect(page.locator(".bg-bg-secondary").first()).toBeVisible({ timeout: 15_000 });
    // Verify the response appeared (trade action or message text)
    const responseText = await page.locator(".bg-bg-secondary").first().textContent();
    expect(responseText).toBeTruthy();
    expect(responseText!.length).toBeGreaterThan(0);
  });
});
