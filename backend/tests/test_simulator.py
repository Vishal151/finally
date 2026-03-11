"""Tests for the SimulatorMarketData implementation."""

import asyncio

import pytest

from src.market.simulator import SimulatorMarketData


@pytest.fixture
def simulator():
    return SimulatorMarketData(tick_interval=0.05, seed=42)


def test_register_and_get_latest_before_start(simulator):
    simulator.register_ticker("AAPL")
    # Before start, cache is empty (no ticks yet)
    assert simulator.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_start_produces_prices(simulator):
    simulator.register_ticker("AAPL")
    simulator.register_ticker("GOOGL")
    await simulator.start()
    await asyncio.sleep(0.15)  # Allow a few ticks
    await simulator.stop()

    aapl = simulator.get_latest("AAPL")
    assert aapl is not None
    assert aapl.ticker == "AAPL"
    assert aapl.price > 0

    googl = simulator.get_latest("GOOGL")
    assert googl is not None


@pytest.mark.asyncio
async def test_get_all_latest(simulator):
    simulator.register_ticker("AAPL")
    simulator.register_ticker("MSFT")
    await simulator.start()
    await asyncio.sleep(0.15)
    await simulator.stop()

    all_prices = simulator.get_all_latest()
    assert len(all_prices) == 2
    assert "AAPL" in all_prices
    assert "MSFT" in all_prices


@pytest.mark.asyncio
async def test_unregister_removes_from_cache(simulator):
    simulator.register_ticker("AAPL")
    await simulator.start()
    await asyncio.sleep(0.15)
    simulator.unregister_ticker("AAPL")
    await simulator.stop()

    assert simulator.get_latest("AAPL") is None


@pytest.mark.asyncio
async def test_stop_is_idempotent(simulator):
    await simulator.start()
    await simulator.stop()
    await simulator.stop()  # Should not raise


def test_implements_interface():
    from src.market.interface import MarketDataSource
    assert issubclass(SimulatorMarketData, MarketDataSource)
