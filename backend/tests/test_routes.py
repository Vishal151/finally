"""Unit tests for API routes."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Use in-memory database and mock LLM for tests
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["LLM_MOCK"] = "true"

from src.app import app
from src.database.db import reset_db


@pytest.fixture(autouse=True)
def _fresh_db():
    """Reset database before each test."""
    reset_db()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestPortfolio:
    def test_get_portfolio_initial(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash_balance"] == 10000.0
        assert data["positions"] == []
        assert data["total_value"] == 10000.0

    def test_buy_trade(self, client):
        # Need to wait for market data to have prices
        # The simulator starts on app startup, give it a moment
        import time
        time.sleep(1)

        resp = client.post("/api/portfolio/trade", json={
            "ticker": "AAPL",
            "quantity": 10,
            "side": "buy",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["trade"]["ticker"] == "AAPL"
        assert data["trade"]["side"] == "buy"
        assert data["trade"]["quantity"] == 10
        assert data["cash_balance"] < 10000.0
        assert data["position"]["ticker"] == "AAPL"
        assert data["position"]["quantity"] == 10

    def test_sell_without_position(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "AAPL",
            "quantity": 10,
            "side": "sell",
        })
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_buy_insufficient_cash(self, client):
        import time
        time.sleep(1)

        resp = client.post("/api/portfolio/trade", json={
            "ticker": "AAPL",
            "quantity": 1000000,
            "side": "buy",
        })
        assert resp.status_code == 400
        assert "Insufficient cash" in resp.json()["error"]

    def test_invalid_side(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "AAPL",
            "quantity": 10,
            "side": "short",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_negative_quantity(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "AAPL",
            "quantity": -5,
            "side": "buy",
        })
        assert resp.status_code == 422

    def test_portfolio_history(self, client):
        resp = client.get("/api/portfolio/history")
        assert resp.status_code == 200
        assert "snapshots" in resp.json()


class TestWatchlist:
    def test_get_watchlist(self, client):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["watchlist"]) == 10
        tickers = [item["ticker"] for item in data["watchlist"]]
        assert "AAPL" in tickers

    def test_add_ticker(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "PYPL"})
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "PYPL"

        # Verify it shows up
        resp = client.get("/api/watchlist")
        tickers = [item["ticker"] for item in resp.json()["watchlist"]]
        assert "PYPL" in tickers

    def test_add_duplicate(self, client):
        resp = client.post("/api/watchlist", json={"ticker": "AAPL"})
        assert resp.status_code == 400

    def test_remove_ticker(self, client):
        resp = client.delete("/api/watchlist/AAPL")
        assert resp.status_code == 200
        assert resp.json()["removed"] == "AAPL"

        resp = client.get("/api/watchlist")
        tickers = [item["ticker"] for item in resp.json()["watchlist"]]
        assert "AAPL" not in tickers

    def test_remove_nonexistent(self, client):
        resp = client.delete("/api/watchlist/ZZZZ")
        assert resp.status_code == 404


class TestChat:
    def test_chat_default_response(self, client):
        resp = client.post("/api/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert data["trades"] == []
        assert data["trade_errors"] == []
        assert data["watchlist_changes"] == []

    def test_chat_buy_triggers_trade(self, client):
        import time
        time.sleep(1)
        resp = client.post("/api/chat", json={"message": "buy 5 AAPL"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["trades"]) == 1
        assert data["trades"][0]["ticker"] == "AAPL"
        assert data["trades"][0]["side"] == "buy"

    def test_chat_history(self, client):
        # Send a message first to populate history
        client.post("/api/chat", json={"message": "Hello"})

        resp = client.get("/api/chat/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert len(data["messages"]) == 2  # user + assistant
        roles = {m["role"] for m in data["messages"]}
        assert roles == {"user", "assistant"}
        # Verify expected fields present
        for msg in data["messages"]:
            assert "id" in msg
            assert "content" in msg
            assert "created_at" in msg
