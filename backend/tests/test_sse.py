"""Tests for the SSE streaming endpoint."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from src.market.models import PriceUpdate
from src.market.sse import router, stream_prices


def _make_app(prices: dict[str, PriceUpdate] | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    source = MagicMock()
    source.get_all_latest.return_value = prices or {}
    app.state.market_data = source
    return app


def _make_request(app: FastAPI, disconnect_after: int = 1):
    """Create a mock Request that disconnects after N iterations."""
    request = MagicMock()
    request.app = app
    call_count = 0

    async def is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count > disconnect_after

    request.is_disconnected = is_disconnected
    return request


@pytest.mark.asyncio
async def test_sse_returns_streaming_response():
    app = _make_app()
    request = _make_request(app)
    resp = await stream_prices(request)
    assert resp.media_type == "text/event-stream"
    assert resp.headers["Cache-Control"] == "no-cache"
    assert resp.headers["X-Accel-Buffering"] == "no"


@pytest.mark.asyncio
async def test_sse_retry_directive():
    app = _make_app()
    request = _make_request(app, disconnect_after=0)
    resp = await stream_prices(request)

    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)

    assert any("retry: 1000" in c for c in chunks)


@pytest.mark.asyncio
async def test_sse_emits_valid_events():
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    prices = {
        "AAPL": PriceUpdate(
            ticker="AAPL", price=191.25, prev_price=190.80,
            timestamp=ts, direction="up",
        ),
    }
    app = _make_app(prices)
    request = _make_request(app, disconnect_after=1)
    resp = await stream_prices(request)

    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)

    all_text = "".join(chunks)
    data_lines = [l for l in all_text.split("\n") if l.startswith("data: ")]
    assert len(data_lines) >= 1

    payload = json.loads(data_lines[0].removeprefix("data: "))
    assert payload["ticker"] == "AAPL"
    assert payload["price"] == 191.25
    assert payload["prev_price"] == 190.80
    assert payload["direction"] == "up"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_sse_empty_cache_no_data_events():
    app = _make_app(prices={})
    request = _make_request(app, disconnect_after=1)
    resp = await stream_prices(request)

    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)

    all_text = "".join(chunks)
    data_lines = [l for l in all_text.split("\n") if l.startswith("data: ")]
    assert len(data_lines) == 0
