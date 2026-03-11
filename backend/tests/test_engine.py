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


def test_sector_correlation():
    """Same-sector tickers should be more correlated than cross-sector.

    Uses a large tick_interval (1 hour) so GBM moves are large enough
    for sector correlation to dominate over random event noise.
    """
    engine = SimulationEngine(tick_interval=3600, seed=42)
    engine.add_ticker("AAPL")   # tech
    engine.add_ticker("MSFT")   # tech
    engine.add_ticker("JPM")    # finance

    n_ticks = 2000
    aapl_returns = []
    msft_returns = []
    jpm_returns = []

    prev = engine.tick()
    for _ in range(n_ticks):
        curr = engine.tick()
        aapl_returns.append(curr["AAPL"] / prev["AAPL"] - 1)
        msft_returns.append(curr["MSFT"] / prev["MSFT"] - 1)
        jpm_returns.append(curr["JPM"] / prev["JPM"] - 1)
        prev = curr

    def correlation(xs, ys):
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / n
        std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
        std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5
        if std_x == 0 or std_y == 0:
            return 0.0
        return cov / (std_x * std_y)

    intra_sector_corr = correlation(aapl_returns, msft_returns)
    cross_sector_corr = abs(correlation(aapl_returns, jpm_returns))
    assert intra_sector_corr > cross_sector_corr


def test_event_mechanism_fires():
    """Over many ticks, the 2% random event mechanism should fire at least once."""
    engine = SimulationEngine(seed=42)
    engine.add_ticker("AAPL")

    prices = []
    for _ in range(500):
        result = engine.tick()
        prices.append(result["AAPL"])

    # Look for large tick-to-tick moves (>1.5% in a single tick) as evidence of events
    large_moves = 0
    for i in range(1, len(prices)):
        pct_change = abs(prices[i] / prices[i - 1] - 1)
        if pct_change > 0.015:
            large_moves += 1

    # With 2% event probability over 500 ticks, we expect ~10 events
    assert large_moves >= 1
