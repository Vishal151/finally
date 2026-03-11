"""Tests for the MassiveMarketData implementation."""

import asyncio
import json

import httpx
import pytest

from src.market.massive_client import MassiveMarketData


def test_implements_interface():
    from src.market.interface import MarketDataSource
    assert issubclass(MassiveMarketData, MarketDataSource)


def test_register_and_unregister():
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")
    client.register_ticker("googl")  # Should uppercase
    assert len(client._tickers) == 2
    assert "AAPL" in client._tickers
    assert "GOOGL" in client._tickers

    client.unregister_ticker("AAPL")
    assert "AAPL" not in client._tickers


def test_get_latest_returns_none_before_poll():
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")
    assert client.get_latest("AAPL") is None


def test_get_all_latest_empty():
    client = MassiveMarketData(api_key="test-key")
    assert client.get_all_latest() == {}


@pytest.mark.asyncio
async def test_fetch_and_update_parses_response():
    """Test that _fetch_and_update correctly parses Massive API response."""
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")
    client.register_ticker("GOOGL")

    mock_response = {
        "count": 2,
        "status": "OK",
        "tickers": [
            {
                "ticker": "AAPL",
                "lastTrade": {"p": 191.25},
                "prevDay": {"c": 190.00},
            },
            {
                "ticker": "GOOGL",
                "lastTrade": {"p": 175.42},
                "prevDay": {"c": 174.00},
            },
        ],
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_response)
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    aapl = client.get_latest("AAPL")
    assert aapl is not None
    assert aapl.price == 191.25

    googl = client.get_latest("GOOGL")
    assert googl is not None
    assert googl.price == 175.42


@pytest.mark.asyncio
async def test_fetch_handles_rate_limit():
    """Test that 429 responses don't crash the client."""
    client = MassiveMarketData(api_key="test-key", poll_interval=0.01)
    client.register_ticker("AAPL")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(429, text="Rate limited")
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    assert client._consecutive_errors == 1
    assert client.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_fetch_handles_network_error():
    """Test that network errors don't crash the client."""
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")

    def raise_error(request):
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(raise_error)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    assert client._consecutive_errors == 1


@pytest.mark.asyncio
async def test_fetch_handles_missing_last_trade():
    """Test that tickers without lastTrade.p are skipped."""
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")

    mock_response = {
        "tickers": [
            {"ticker": "AAPL", "lastTrade": {}},
        ],
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_response)
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    assert client.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_fetch_handles_auth_error():
    """Test that 401 responses don't crash the client."""
    client = MassiveMarketData(api_key="bad-key")
    client.register_ticker("AAPL")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, text="Unauthorized")
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    assert client._consecutive_errors == 1
    assert client.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_fetch_handles_forbidden():
    """Test that 403 responses don't crash the client."""
    client = MassiveMarketData(api_key="test-key")
    client.register_ticker("AAPL")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(403, text="Forbidden")
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await client._fetch_and_update(mock_client)

    assert client._consecutive_errors == 1
    assert client.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    client = MassiveMarketData(api_key="test-key")
    await client.stop()
    await client.stop()  # Should not raise
