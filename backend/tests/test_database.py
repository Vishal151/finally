"""Tests for database layer."""

import os
import sqlite3

import pytest

# Use in-memory database for tests
os.environ["DATABASE_PATH"] = ":memory:"

from src.database.db import close_db, get_db, init_db
from src.database import queries


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the database connection before each test."""
    close_db()
    # Force a fresh in-memory DB
    import src.database.db as db_mod
    db_mod._connection = None
    yield
    close_db()


class TestInitialization:
    def test_lazy_init_creates_tables(self):
        conn = get_db()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        assert "users_profile" in tables
        assert "watchlist" in tables
        assert "positions" in tables
        assert "trades" in tables
        assert "portfolio_snapshots" in tables
        assert "chat_messages" in tables

    def test_seed_data_default_user(self):
        profile = queries.get_portfolio()
        assert profile["id"] == "default"
        assert profile["cash_balance"] == 10000.0

    def test_seed_data_watchlist(self):
        tickers = queries.get_watchlist_tickers()
        assert len(tickers) == 10
        assert "AAPL" in tickers
        assert "NFLX" in tickers

    def test_init_is_idempotent(self):
        conn = get_db()
        init_db(conn)  # second call should not raise
        assert queries.get_portfolio()["cash_balance"] == 10000.0


class TestTrades:
    def test_buy_reduces_cash(self):
        queries.execute_trade("AAPL", "buy", 10, 100.0)
        profile = queries.get_portfolio()
        assert profile["cash_balance"] == 9000.0

    def test_buy_creates_position(self):
        queries.execute_trade("AAPL", "buy", 5, 200.0)
        pos = queries.get_position("AAPL")
        assert pos is not None
        assert pos["quantity"] == 5
        assert pos["avg_cost"] == 200.0

    def test_buy_updates_avg_cost(self):
        queries.execute_trade("AAPL", "buy", 10, 100.0)
        queries.execute_trade("AAPL", "buy", 10, 200.0)
        pos = queries.get_position("AAPL")
        assert pos["quantity"] == 20
        assert pos["avg_cost"] == 150.0

    def test_sell_increases_cash(self):
        queries.execute_trade("AAPL", "buy", 10, 100.0)
        queries.execute_trade("AAPL", "sell", 5, 150.0)
        profile = queries.get_portfolio()
        assert profile["cash_balance"] == 9750.0

    def test_full_sell_deletes_position(self):
        queries.execute_trade("AAPL", "buy", 10, 100.0)
        queries.execute_trade("AAPL", "sell", 10, 150.0)
        pos = queries.get_position("AAPL")
        assert pos is None

    def test_sell_without_position_raises(self):
        with pytest.raises(ValueError, match="No position"):
            queries.execute_trade("AAPL", "sell", 5, 100.0)

    def test_sell_more_than_owned_raises(self):
        queries.execute_trade("AAPL", "buy", 5, 100.0)
        with pytest.raises(ValueError, match="Insufficient shares"):
            queries.execute_trade("AAPL", "sell", 10, 100.0)

    def test_buy_insufficient_cash_raises(self):
        with pytest.raises(ValueError, match="Insufficient cash"):
            queries.execute_trade("AAPL", "buy", 1000, 100.0)

    def test_trade_returns_record(self):
        trade = queries.execute_trade("AAPL", "buy", 5, 100.0)
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 5
        assert trade["price"] == 100.0
        assert "id" in trade
        assert "executed_at" in trade

    def test_trade_history(self):
        queries.execute_trade("AAPL", "buy", 10, 100.0)
        queries.execute_trade("AAPL", "sell", 5, 150.0)
        trades = queries.get_trades()
        assert len(trades) == 2
        assert trades[0]["side"] == "sell"  # DESC order
        assert trades[1]["side"] == "buy"

    def test_invalid_side_raises(self):
        with pytest.raises(ValueError, match="Invalid side"):
            queries.execute_trade("AAPL", "short", 5, 100.0)


class TestWatchlist:
    def test_add_ticker(self):
        # Remove a seeded one first then add a new one
        queries.remove_from_watchlist("AAPL")
        entry = queries.add_to_watchlist("PYPL")
        assert entry["ticker"] == "PYPL"
        assert "id" in entry

    def test_add_duplicate_raises(self):
        with pytest.raises(ValueError, match="already in watchlist"):
            queries.add_to_watchlist("AAPL")  # already seeded

    def test_remove_ticker(self):
        assert queries.remove_from_watchlist("AAPL") is True
        tickers = queries.get_watchlist_tickers()
        assert "AAPL" not in tickers

    def test_remove_nonexistent(self):
        assert queries.remove_from_watchlist("ZZZZ") is False

    def test_get_watchlist_returns_dicts(self):
        wl = queries.get_watchlist()
        assert len(wl) == 10
        assert "ticker" in wl[0]
        assert "added_at" in wl[0]


class TestSnapshots:
    def test_record_and_get(self):
        queries.record_snapshot(10500.0)
        queries.record_snapshot(10200.0)
        snaps = queries.get_snapshots()
        assert len(snaps) == 2
        assert snaps[0]["total_value"] == 10500.0
        assert snaps[1]["total_value"] == 10200.0


class TestChat:
    def test_save_user_message(self):
        msg = queries.save_chat_message("user", "Hello")
        assert msg["role"] == "user"
        assert msg["content"] == "Hello"
        assert msg["actions"] is None

    def test_save_assistant_message_with_actions(self):
        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
        msg = queries.save_chat_message("assistant", "Bought AAPL", actions)
        assert msg["actions"] == actions

    def test_chat_history_limit(self):
        for i in range(25):
            queries.save_chat_message("user", f"Message {i}")
        history = queries.get_chat_history(limit=20)
        assert len(history) == 20
        # Should be the most recent 20, oldest first
        assert history[0]["content"] == "Message 5"
        assert history[-1]["content"] == "Message 24"

    def test_chat_history_actions_deserialized(self):
        actions = {"trades": []}
        queries.save_chat_message("assistant", "Done", actions)
        history = queries.get_chat_history()
        assert history[-1]["actions"] == actions
