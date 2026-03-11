"""All database query functions for FinAlly."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .db import get_db

DEFAULT_USER = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Portfolio ---

def get_portfolio(user_id: str = DEFAULT_USER) -> dict:
    """Get user profile with cash balance."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return {"id": user_id, "cash_balance": 0.0, "created_at": None}
    return dict(row)


def get_positions(user_id: str = DEFAULT_USER) -> list[dict]:
    """Get all open positions for a user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(ticker: str, user_id: str = DEFAULT_USER) -> dict | None:
    """Get a single position by ticker."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row) if row else None


def execute_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER
) -> dict:
    """Execute a trade. Returns the trade record.

    Raises ValueError on validation failure (insufficient cash/shares).
    """
    conn = get_db()
    profile = get_portfolio(user_id)
    cash = profile["cash_balance"]
    total_cost = round(price * quantity, 2)

    if side == "buy":
        if total_cost > cash:
            raise ValueError(f"Insufficient cash: need ${total_cost:.2f}, have ${cash:.2f}")
        new_cash = round(cash - total_cost, 2)
        # Update or create position
        existing = get_position(ticker, user_id)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = round(
                (existing["avg_cost"] * existing["quantity"] + price * quantity) / new_qty, 2
            )
            conn.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                "WHERE user_id = ? AND ticker = ?",
                (new_qty, new_avg, _now(), user_id, ticker),
            )
        else:
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_uuid(), user_id, ticker, quantity, price, _now()),
            )
    elif side == "sell":
        existing = get_position(ticker, user_id)
        if not existing:
            raise ValueError(f"No position in {ticker}")
        if quantity > existing["quantity"]:
            raise ValueError(
                f"Insufficient shares: want to sell {quantity}, have {existing['quantity']}"
            )
        new_cash = round(cash + total_cost, 2)
        new_qty = existing["quantity"] - quantity
        if new_qty < 1e-9:  # effectively zero
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
        else:
            conn.execute(
                "UPDATE positions SET quantity = ?, updated_at = ? "
                "WHERE user_id = ? AND ticker = ?",
                (new_qty, _now(), user_id, ticker),
            )
    else:
        raise ValueError(f"Invalid side: {side}")

    # Update cash
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (new_cash, user_id),
    )

    # Record trade
    trade_id = _uuid()
    executed_at = _now()
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (trade_id, user_id, ticker, side, quantity, price, executed_at),
    )
    conn.commit()

    return {
        "id": trade_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": executed_at,
    }


def get_trades(user_id: str = DEFAULT_USER) -> list[dict]:
    """Get trade history."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, ticker, side, quantity, price, executed_at "
        "FROM trades WHERE user_id = ? ORDER BY executed_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- Watchlist ---

def get_watchlist(user_id: str = DEFAULT_USER) -> list[dict]:
    """Get all watchlist entries."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, ticker, added_at "
        "FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_watchlist_tickers(user_id: str = DEFAULT_USER) -> list[str]:
    """Get just the ticker symbols from the watchlist."""
    conn = get_db()
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    ).fetchall()
    return [r["ticker"] for r in rows]


def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER) -> dict:
    """Add a ticker to the watchlist. Returns the entry. Raises ValueError if duplicate."""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    if existing:
        raise ValueError(f"{ticker} already in watchlist")
    entry_id = _uuid()
    added_at = _now()
    conn.execute(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (entry_id, user_id, ticker, added_at),
    )
    conn.commit()
    return {"id": entry_id, "user_id": user_id, "ticker": ticker, "added_at": added_at}


def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER) -> bool:
    """Remove a ticker from the watchlist. Returns True if removed."""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    conn.commit()
    return cursor.rowcount > 0


# --- Portfolio Snapshots ---

def record_snapshot(total_value: float, user_id: str = DEFAULT_USER) -> dict:
    """Record a portfolio value snapshot."""
    conn = get_db()
    snap_id = _uuid()
    recorded_at = _now()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (snap_id, user_id, total_value, recorded_at),
    )
    conn.commit()
    return {"id": snap_id, "total_value": total_value, "recorded_at": recorded_at}


def get_snapshots(user_id: str = DEFAULT_USER) -> list[dict]:
    """Get portfolio snapshots ordered by time."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, total_value, recorded_at "
        "FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- Chat Messages ---

def save_chat_message(
    role: str, content: str, actions: dict | None = None, user_id: str = DEFAULT_USER
) -> dict:
    """Save a chat message."""
    conn = get_db()
    msg_id = _uuid()
    created_at = _now()
    actions_json = json.dumps(actions) if actions else None
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, user_id, role, content, actions_json, created_at),
    )
    conn.commit()
    return {
        "id": msg_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": created_at,
    }


def get_chat_history(limit: int = 20, user_id: str = DEFAULT_USER) -> list[dict]:
    """Get recent chat messages, oldest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, role, content, actions, created_at "
        "FROM chat_messages WHERE user_id = ? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    results = []
    for r in reversed(rows):
        d = dict(r)
        if d["actions"]:
            d["actions"] = json.loads(d["actions"])
        results.append(d)
    return results
