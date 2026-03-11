"""Mock LLM for testing and development without an API key."""

from __future__ import annotations

from .models import LLMResponse


def mock_llm_response(user_message: str, portfolio_context: str) -> LLMResponse:
    """Return deterministic responses based on input patterns."""
    msg_lower = user_message.lower()

    # Buy pattern
    if "buy" in msg_lower:
        ticker = _extract_ticker(msg_lower) or "AAPL"
        qty = _extract_quantity(msg_lower) or 5
        return LLMResponse(
            message=f"Executing buy order: {qty} shares of {ticker}.",
            trades=[{"ticker": ticker, "side": "buy", "quantity": qty}],
            watchlist_changes=[],
        )

    # Sell pattern
    if "sell" in msg_lower:
        ticker = _extract_ticker(msg_lower) or "AAPL"
        qty = _extract_quantity(msg_lower) or 5
        return LLMResponse(
            message=f"Executing sell order: {qty} shares of {ticker}.",
            trades=[{"ticker": ticker, "side": "sell", "quantity": qty}],
            watchlist_changes=[],
        )

    # Add to watchlist
    if "add" in msg_lower and "watchlist" in msg_lower:
        ticker = _extract_ticker(msg_lower) or "PYPL"
        return LLMResponse(
            message=f"Adding {ticker} to your watchlist.",
            trades=[],
            watchlist_changes=[{"ticker": ticker, "action": "add"}],
        )

    # Remove from watchlist
    if "remove" in msg_lower and "watchlist" in msg_lower:
        ticker = _extract_ticker(msg_lower) or "PYPL"
        return LLMResponse(
            message=f"Removing {ticker} from your watchlist.",
            trades=[],
            watchlist_changes=[{"ticker": ticker, "action": "remove"}],
        )

    # Portfolio analysis
    if any(word in msg_lower for word in ["portfolio", "position", "holdings", "balance"]):
        return LLMResponse(
            message="Your portfolio looks well-diversified. Consider reviewing positions with significant unrealized losses.",
            trades=[],
            watchlist_changes=[],
        )

    # Default response
    return LLMResponse(
        message="I can help you analyze your portfolio, execute trades, or manage your watchlist. What would you like to do?",
        trades=[],
        watchlist_changes=[],
    )


_KNOWN_TICKERS = {
    "aapl", "googl", "msft", "amzn", "tsla", "nvda", "meta", "jpm", "v", "nflx",
    "pypl", "dis", "baba", "crm", "amd", "intc", "nke", "ko", "pep",
}


def _extract_ticker(text: str) -> str | None:
    """Extract a ticker symbol from user text."""
    words = text.upper().split()
    for word in words:
        cleaned = word.strip(".,!?;:")
        if cleaned.isalpha() and len(cleaned) <= 5 and cleaned.lower() in _KNOWN_TICKERS:
            return cleaned
    return None


def _extract_quantity(text: str) -> int | None:
    """Extract a numeric quantity from user text."""
    words = text.split()
    for word in words:
        try:
            val = int(word)
            if 0 < val < 100000:
                return val
        except ValueError:
            continue
    return None
