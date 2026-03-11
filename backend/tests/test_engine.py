"""Tests for the GBM simulation engine."""

from src.market.engine import SimulationEngine
from src.market.seed_prices import SEED_PRICES


def test_add_known_ticker_uses_seed_price():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    assert engine.get_current_price("AAPL") == SEED_PRICES["AAPL"]


def test_add_ticker_with_explicit_seed_price():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL", seed_price=100.0)
    assert engine.get_current_price("AAPL") == 100.0


def test_add_unknown_ticker_gets_random_price():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("XYZ")
    price = engine.get_current_price("XYZ")
    assert price is not None
    assert 50.0 <= price <= 300.0


def test_add_ticker_is_case_insensitive():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("aapl")
    assert engine.get_current_price("AAPL") is not None


def test_add_duplicate_is_noop():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    price_before = engine.get_current_price("AAPL")
    engine.add_ticker("AAPL", seed_price=999.0)
    assert engine.get_current_price("AAPL") == price_before


def test_remove_ticker():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    engine.remove_ticker("AAPL")
    assert engine.get_current_price("AAPL") is None
    assert "AAPL" not in engine.tracked_tickers


def test_tick_returns_empty_with_no_tickers():
    engine = SimulationEngine(seed=42)
    result = engine.tick()
    assert result == {}


def test_tick_returns_prices_for_all_tickers():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    engine.add_ticker("GOOGL")
    result = engine.tick()
    assert "AAPL" in result
    assert "GOOGL" in result


def test_tick_produces_positive_prices():
    engine = SimulationEngine(seed=42)
    for ticker in SEED_PRICES:
        engine.add_ticker(ticker)
    for _ in range(1000):
        result = engine.tick()
        for price in result.values():
            assert price > 0


def test_tick_is_deterministic_with_seed():
    engine1 = SimulationEngine(seed=123)
    engine2 = SimulationEngine(seed=123)
    for ticker in ["AAPL", "GOOGL", "MSFT"]:
        engine1.add_ticker(ticker)
        engine2.add_ticker(ticker)
    result1 = engine1.tick()
    result2 = engine2.tick()
    assert result1 == result2


def test_prices_change_over_ticks():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    prices = set()
    for _ in range(100):
        result = engine.tick()
        prices.add(result["AAPL"])
    # Over 100 ticks, we should see more than 1 unique price
    assert len(prices) > 1


def test_tracked_tickers():
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")
    engine.add_ticker("GOOGL")
    assert sorted(engine.tracked_tickers) == ["AAPL", "GOOGL"]


def test_get_current_price_unknown_ticker():
    engine = SimulationEngine(seed=42)
    assert engine.get_current_price("UNKNOWN") is None
