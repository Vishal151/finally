"""Tests for PriceUpdate data model."""

from datetime import datetime, timezone

from src.market.models import PriceUpdate


def test_price_update_fields():
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    update = PriceUpdate(
        ticker="AAPL", price=191.25, prev_price=190.80,
        timestamp=ts, direction="up",
    )
    assert update.ticker == "AAPL"
    assert update.price == 191.25
    assert update.prev_price == 190.80
    assert update.direction == "up"


def test_price_update_is_frozen():
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    update = PriceUpdate(
        ticker="AAPL", price=191.25, prev_price=190.80,
        timestamp=ts, direction="up",
    )
    try:
        update.price = 200.0  # type: ignore[misc]
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_to_dict():
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    update = PriceUpdate(
        ticker="AAPL", price=191.25, prev_price=190.80,
        timestamp=ts, direction="up",
    )
    d = update.to_dict()
    assert d["ticker"] == "AAPL"
    assert d["price"] == 191.25
    assert d["prev_price"] == 190.80
    assert d["timestamp"] == "2025-01-15T14:30:00+00:00"
    assert d["direction"] == "up"
