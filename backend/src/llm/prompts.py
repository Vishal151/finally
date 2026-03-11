"""System prompt and message formatting for the FinAlly AI trading assistant."""

SYSTEM_PROMPT = """\
You are FinAlly, an AI trading assistant embedded in a simulated trading workstation.

You have access to the user's portfolio and can execute trades and manage the watchlist.

Capabilities:
- Analyze portfolio composition, concentration risk, and P&L
- Suggest trades with clear reasoning
- Execute buy/sell market orders when the user asks or agrees
- Add/remove tickers from the watchlist

Style:
- Be concise and data-driven
- Lead with numbers and facts
- Use short paragraphs

You MUST respond with valid JSON matching this exact schema:
{
  "message": "Your conversational response to the user",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}

Rules:
- "message" is required and must be a non-empty string
- "trades" is optional (omit or use empty array if no trades)
- "watchlist_changes" is optional (omit or use empty array if no changes)
- "side" must be "buy" or "sell"
- "action" must be "add" or "remove"
- "quantity" must be a positive number
- Only suggest trades the user can afford (check cash for buys, shares for sells)
"""


def format_portfolio_context(
    cash: float,
    positions: list[dict],
    watchlist_prices: list[dict],
    total_value: float,
) -> str:
    """Format the user's portfolio state as context for the LLM."""
    lines = [
        f"Portfolio Value: ${total_value:,.2f}",
        f"Cash: ${cash:,.2f}",
    ]

    if positions:
        lines.append("\nPositions:")
        for p in positions:
            pnl = (p["current_price"] - p["avg_cost"]) * p["quantity"]
            pct = ((p["current_price"] / p["avg_cost"]) - 1) * 100 if p["avg_cost"] > 0 else 0
            lines.append(
                f"  {p['ticker']}: {p['quantity']} shares @ ${p['avg_cost']:.2f} avg | "
                f"now ${p['current_price']:.2f} | P&L: ${pnl:,.2f} ({pct:+.1f}%)"
            )
    else:
        lines.append("\nNo positions held.")

    if watchlist_prices:
        lines.append("\nWatchlist:")
        for w in watchlist_prices:
            lines.append(f"  {w['ticker']}: ${w['price']:.2f}")

    return "\n".join(lines)


def build_messages(
    portfolio_context: str,
    history: list[dict],
    user_message: str,
) -> list[dict]:
    """Build the messages list for the LLM call."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio state:\n{portfolio_context}"},
    ]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages
