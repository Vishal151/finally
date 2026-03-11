"""Tests for PriceCache."""

from datetime import datetime, timezone

from src.market.cache import PriceCache


def test_first_update_direction_is_unchanged():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    update = cache.update("AAPL", 190.0, ts)
    assert update.direction == "unchanged"
    assert update.prev_price == 190.0


def test_price_up():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    cache.update("AAPL", 190.0, ts)
    update = cache.update("AAPL", 191.0, ts)
    assert update.direction == "up"
    assert update.prev_price == 190.0
    assert update.price == 191.0


def test_price_down():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    cache.update("AAPL", 190.0, ts)
    update = cache.update("AAPL", 189.0, ts)
    assert update.direction == "down"
    assert update.prev_price == 190.0


def test_get_returns_none_for_unknown():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_get_returns_latest():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    cache.update("AAPL", 190.0, ts)
    assert cache.get("AAPL") is not None
    assert cache.get("AAPL").price == 190.0


def test_get_all():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    cache.update("AAPL", 190.0, ts)
    cache.update("GOOGL", 175.0, ts)
    all_prices = cache.get_all()
    assert len(all_prices) == 2
    assert "AAPL" in all_prices
    assert "GOOGL" in all_prices


def test_remove():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    cache.update("AAPL", 190.0, ts)
    cache.remove("AAPL")
    assert cache.get("AAPL") is None
    assert "AAPL" not in cache.tickers


def test_remove_nonexistent_is_noop():
    cache = PriceCache()
    cache.remove("AAPL")  # should not raise


def test_prices_are_rounded():
    cache = PriceCache()
    ts = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
    update = cache.update("AAPL", 190.123456, ts)
    assert update.price == 190.12
