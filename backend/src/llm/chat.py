"""Main chat handler -- orchestrates LLM calls, trade execution, and persistence."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from litellm import completion

from ..database import get_db
from ..market.cache import PriceCache
from .mock import mock_llm_response
from .models import LLMResponse
from .prompts import build_messages, format_portfolio_context

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
HISTORY_LIMIT = 20


def handle_chat_message(
    user_message: str,
    price_cache: PriceCache,
    user_id: str = "default",
) -> dict:
    """Process a user chat message and return the assistant's response with executed actions.

    Steps:
    1. Load portfolio context (cash, positions, watchlist, prices)
    2. Load conversation history (last 20 messages)
    3. Call LLM (or mock) for structured response
    4. Auto-execute trades and watchlist changes
    5. Store messages in chat_messages table
    6. Return response dict
    """
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()

    # 1. Load portfolio context
    cash = _get_cash_balance(conn, user_id)
    positions = _get_positions_with_prices(conn, user_id, price_cache)
    watchlist_prices = _get_watchlist_prices(conn, user_id, price_cache)
    total_value = cash + sum(p["current_price"] * p["quantity"] for p in positions)

    portfolio_context = format_portfolio_context(cash, positions, watchlist_prices, total_value)

    # 2. Load conversation history
    history = _get_chat_history(conn, user_id)

    # 3. Call LLM or mock
    use_mock = os.environ.get("LLM_MOCK", "").lower() == "true"

    if use_mock:
        llm_response = mock_llm_response(user_message, portfolio_context)
    else:
        llm_response = _call_llm(portfolio_context, history, user_message)

    # 4. Auto-execute trades and watchlist changes
    trade_results = []
    trade_errors = []
    for trade in llm_response.trades:
        result = _execute_trade(
            conn, user_id, trade.ticker.upper(), trade.side, trade.quantity, price_cache,
        )
        if "error" in result:
            trade_errors.append(result)
        else:
            trade_results.append(result)

    watchlist_results = []
    for change in llm_response.watchlist_changes:
        result = _execute_watchlist_change(conn, user_id, change.ticker.upper(), change.action, price_cache)
        watchlist_results.append(result)

    # 5. Store messages
    actions = {
        "trades": trade_results,
        "trade_errors": trade_errors,
        "watchlist_changes": watchlist_results,
    }

    _store_message(conn, user_id, "user", user_message, None, now)
    _store_message(conn, user_id, "assistant", llm_response.message, actions, now)

    # 6. Return response
    return {
        "message": llm_response.message,
        "trades": trade_results,
        "trade_errors": trade_errors,
        "watchlist_changes": watchlist_results,
    }


def _call_llm(
    portfolio_context: str,
    history: list[dict],
    user_message: str,
) -> LLMResponse:
    """Call the LLM via LiteLLM/OpenRouter with structured output."""
    messages = build_messages(portfolio_context, history, user_message)

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )

    content = response.choices[0].message.content
    return LLMResponse.model_validate_json(content)


# -- Database helpers --


def _get_cash_balance(conn, user_id: str) -> float:
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    return row["cash_balance"] if row else 10000.0


def _get_positions_with_prices(conn, user_id: str, price_cache: PriceCache) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ?", (user_id,)
    ).fetchall()
    positions = []
    for row in rows:
        cached = price_cache.get(row["ticker"])
        current_price = cached.price if cached else row["avg_cost"]
        positions.append({
            "ticker": row["ticker"],
            "quantity": row["quantity"],
            "avg_cost": row["avg_cost"],
            "current_price": current_price,
        })
    return positions


def _get_watchlist_prices(conn, user_id: str, price_cache: PriceCache) -> list[dict]:
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ?", (user_id,)
    ).fetchall()
    result = []
    for row in rows:
        cached = price_cache.get(row["ticker"])
        price = cached.price if cached else 0.0
        result.append({"ticker": row["ticker"], "price": price})
    return result


def _get_chat_history(conn, user_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, HISTORY_LIMIT),
    ).fetchall()
    # Reverse to chronological order
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _store_message(conn, user_id: str, role: str, content: str, actions: dict | None, timestamp: str) -> None:
    actions_json = json.dumps(actions) if actions else None
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, role, content, actions_json, timestamp),
    )
    conn.commit()


# -- Trade execution --


def _execute_trade(
    conn, user_id: str, ticker: str, side: str, quantity: float, price_cache: PriceCache,
) -> dict:
    """Execute a single trade. Returns result dict or error dict."""
    cached = price_cache.get(ticker)
    if not cached:
        return {"error": f"No price available for {ticker}"}

    price = cached.price
    now = datetime.now(timezone.utc).isoformat()

    if side == "buy":
        cost = price * quantity
        cash = _get_cash_balance(conn, user_id)
        if cost > cash:
            return {"error": f"Insufficient cash for {ticker}: need ${cost:,.2f}, have ${cash:,.2f}"}

        # Deduct cash
        conn.execute(
            "UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = ?",
            (cost, user_id),
        )

        # Update or create position
        existing = conn.execute(
            "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()

        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = ((existing["avg_cost"] * existing["quantity"]) + (price * quantity)) / new_qty
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
                (new_qty, round(new_avg, 4), now, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, ticker, quantity, price, now),
            )

    elif side == "sell":
        existing = conn.execute(
            "SELECT id, quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        ).fetchone()

        if not existing or existing["quantity"] < quantity:
            have = existing["quantity"] if existing else 0
            return {"error": f"Insufficient shares of {ticker}: need {quantity}, have {have}"}

        proceeds = price * quantity
        conn.execute(
            "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
            (proceeds, user_id),
        )

        new_qty = existing["quantity"] - quantity
        if new_qty < 1e-9:
            conn.execute("DELETE FROM positions WHERE id = ?", (existing["id"],))
        else:
            conn.execute(
                "UPDATE positions SET quantity = ?, updated_at = ? WHERE id = ?",
                (new_qty, now, existing["id"]),
            )
    else:
        return {"error": f"Invalid side: {side}"}

    # Record trade
    trade_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, user_id, ticker, side, quantity, price, now),
    )
    conn.commit()

    return {
        "id": trade_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now,
    }


# -- Watchlist helpers --


def _execute_watchlist_change(
    conn, user_id: str, ticker: str, action: str, price_cache: PriceCache,
) -> dict:
    """Add or remove a ticker from the watchlist."""
    now = datetime.now(timezone.utc).isoformat()

    if action == "add":
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, ticker, now),
        )
        conn.commit()
        # Register with market data source via price cache (the simulator/source
        # is notified separately by the watchlist API layer)
        return {"ticker": ticker, "action": "add", "status": "ok"}

    elif action == "remove":
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        conn.commit()
        return {"ticker": ticker, "action": "remove", "status": "ok"}

    return {"ticker": ticker, "action": action, "status": "error", "error": f"Invalid action: {action}"}
