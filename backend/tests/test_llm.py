"""Tests for the LLM chat integration."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.llm.chat import handle_chat_message, _execute_trade, _get_cash_balance
from src.llm.mock import mock_llm_response
from src.llm.models import LLMResponse
from src.llm.prompts import build_messages, format_portfolio_context
from src.market.cache import PriceCache
from src.market.models import PriceUpdate


@pytest.fixture
def db_conn():
    """Create an in-memory SQLite database with the schema and seed data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    seed_path = Path(__file__).parent.parent / "db" / "seed.sql"

    conn.executescript(schema_path.read_text())
    conn.executescript(seed_path.read_text())
    return conn


@pytest.fixture
def price_cache():
    """Create a price cache with some test prices."""
    cache = PriceCache()
    now = datetime.now(timezone.utc)
    cache.update("AAPL", 190.0, now)
    cache.update("GOOGL", 175.0, now)
    cache.update("MSFT", 420.0, now)
    cache.update("TSLA", 250.0, now)
    cache.update("NVDA", 900.0, now)
    return cache


# -- Models --


class TestLLMResponse:
    def test_parse_full_response(self):
        data = {
            "message": "Buying AAPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
        resp = LLMResponse.model_validate(data)
        assert resp.message == "Buying AAPL"
        assert len(resp.trades) == 1
        assert resp.trades[0].ticker == "AAPL"
        assert len(resp.watchlist_changes) == 1

    def test_parse_minimal_response(self):
        data = {"message": "Hello"}
        resp = LLMResponse.model_validate(data)
        assert resp.message == "Hello"
        assert resp.trades == []
        assert resp.watchlist_changes == []

    def test_parse_from_json_string(self):
        raw = '{"message": "Done", "trades": [], "watchlist_changes": []}'
        resp = LLMResponse.model_validate_json(raw)
        assert resp.message == "Done"


# -- Mock LLM --


class TestMockLLM:
    def test_buy_pattern(self):
        resp = mock_llm_response("buy 10 AAPL", "")
        assert len(resp.trades) == 1
        assert resp.trades[0].side == "buy"
        assert resp.trades[0].ticker == "AAPL"
        assert resp.trades[0].quantity == 10

    def test_sell_pattern(self):
        resp = mock_llm_response("sell 5 MSFT", "")
        assert len(resp.trades) == 1
        assert resp.trades[0].side == "sell"
        assert resp.trades[0].ticker == "MSFT"

    def test_add_watchlist(self):
        resp = mock_llm_response("add PYPL to watchlist", "")
        assert len(resp.watchlist_changes) == 1
        assert resp.watchlist_changes[0].action == "add"
        assert resp.watchlist_changes[0].ticker == "PYPL"

    def test_remove_watchlist(self):
        resp = mock_llm_response("remove PYPL from watchlist", "")
        assert len(resp.watchlist_changes) == 1
        assert resp.watchlist_changes[0].action == "remove"

    def test_portfolio_query(self):
        resp = mock_llm_response("show my portfolio", "")
        assert resp.trades == []
        assert "portfolio" in resp.message.lower() or "diversified" in resp.message.lower()

    def test_default_response(self):
        resp = mock_llm_response("hello there", "")
        assert resp.trades == []
        assert resp.watchlist_changes == []
        assert len(resp.message) > 0


# -- Prompts --


class TestPrompts:
    def test_format_portfolio_context(self):
        ctx = format_portfolio_context(
            cash=5000.0,
            positions=[{
                "ticker": "AAPL",
                "quantity": 10,
                "avg_cost": 180.0,
                "current_price": 190.0,
            }],
            watchlist_prices=[{"ticker": "GOOGL", "price": 175.0}],
            total_value=6900.0,
        )
        assert "$5,000.00" in ctx
        assert "AAPL" in ctx
        assert "GOOGL" in ctx

    def test_format_empty_portfolio(self):
        ctx = format_portfolio_context(
            cash=10000.0, positions=[], watchlist_prices=[], total_value=10000.0,
        )
        assert "No positions" in ctx

    def test_build_messages(self):
        msgs = build_messages(
            "Cash: $10000",
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "buy AAPL",
        )
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "buy AAPL"
        assert len(msgs) == 5  # 2 system + 2 history + 1 user


# -- Trade execution --


class TestTradeExecution:
    def test_buy_success(self, db_conn, price_cache):
        with patch("src.llm.chat.get_db", return_value=db_conn):
            result = _execute_trade(db_conn, "default", "AAPL", "buy", 10, price_cache)
        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["quantity"] == 10
        assert result["price"] == 190.0

        # Cash should be reduced
        cash = db_conn.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'").fetchone()
        assert cash[0] == pytest.approx(10000.0 - 1900.0)

        # Position should exist
        pos = db_conn.execute("SELECT * FROM positions WHERE ticker = 'AAPL'").fetchone()
        assert pos["quantity"] == 10

    def test_buy_insufficient_cash(self, db_conn, price_cache):
        result = _execute_trade(db_conn, "default", "NVDA", "buy", 100, price_cache)
        assert "error" in result
        assert "Insufficient cash" in result["error"]

    def test_sell_no_position(self, db_conn, price_cache):
        result = _execute_trade(db_conn, "default", "AAPL", "sell", 10, price_cache)
        assert "error" in result
        assert "Insufficient shares" in result["error"]

    def test_buy_then_sell(self, db_conn, price_cache):
        _execute_trade(db_conn, "default", "AAPL", "buy", 10, price_cache)
        result = _execute_trade(db_conn, "default", "AAPL", "sell", 10, price_cache)
        assert "error" not in result

        # Position should be deleted
        pos = db_conn.execute("SELECT * FROM positions WHERE ticker = 'AAPL'").fetchone()
        assert pos is None

        # Cash should be back to original
        cash = db_conn.execute("SELECT cash_balance FROM users_profile WHERE id = 'default'").fetchone()
        assert cash[0] == pytest.approx(10000.0)

    def test_buy_averages_cost(self, db_conn, price_cache):
        _execute_trade(db_conn, "default", "AAPL", "buy", 10, price_cache)
        # Update price
        price_cache.update("AAPL", 200.0, datetime.now(timezone.utc))
        _execute_trade(db_conn, "default", "AAPL", "buy", 10, price_cache)

        pos = db_conn.execute("SELECT * FROM positions WHERE ticker = 'AAPL'").fetchone()
        assert pos["quantity"] == 20
        expected_avg = (190.0 * 10 + 200.0 * 10) / 20
        assert pos["avg_cost"] == pytest.approx(expected_avg, rel=1e-3)

    def test_no_price_available(self, db_conn, price_cache):
        result = _execute_trade(db_conn, "default", "FAKE", "buy", 10, price_cache)
        assert "error" in result
        assert "No price" in result["error"]

    def test_invalid_side(self, db_conn, price_cache):
        result = _execute_trade(db_conn, "default", "AAPL", "short", 10, price_cache)
        assert "error" in result
        assert "Invalid side" in result["error"]


# -- Full chat handler (mock mode) --


class TestHandleChatMessage:
    def test_mock_chat_buy(self, db_conn, price_cache):
        with patch("src.llm.chat.get_db", return_value=db_conn), \
             patch.dict(os.environ, {"LLM_MOCK": "true"}):
            result = handle_chat_message("buy 5 AAPL", price_cache)

        assert "message" in result
        assert len(result["trades"]) == 1
        assert result["trades"][0]["ticker"] == "AAPL"

        # Verify messages stored
        msgs = db_conn.execute("SELECT * FROM chat_messages ORDER BY created_at").fetchall()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_mock_chat_portfolio_query(self, db_conn, price_cache):
        with patch("src.llm.chat.get_db", return_value=db_conn), \
             patch.dict(os.environ, {"LLM_MOCK": "true"}):
            result = handle_chat_message("show my portfolio", price_cache)

        assert "message" in result
        assert result["trades"] == []

    def test_mock_chat_insufficient_cash(self, db_conn, price_cache):
        with patch("src.llm.chat.get_db", return_value=db_conn), \
             patch.dict(os.environ, {"LLM_MOCK": "true"}):
            # Try to buy way too much
            result = handle_chat_message("buy 1000 NVDA", price_cache)

        # The mock will try to buy 1000 NVDA at $900 = $900k > $10k cash
        assert len(result["trade_errors"]) == 1
        assert "Insufficient cash" in result["trade_errors"][0]["error"]
