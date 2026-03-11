"""Tests for the market data source factory."""

import os

from src.market.factory import create_market_data_source
from src.market.massive_client import MassiveMarketData
from src.market.simulator import SimulatorMarketData


def test_factory_returns_simulator_by_default(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    source = create_market_data_source()
    assert isinstance(source, SimulatorMarketData)


def test_factory_returns_massive_when_key_set(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key-123")
    source = create_market_data_source()
    assert isinstance(source, MassiveMarketData)


def test_factory_ignores_empty_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "")
    source = create_market_data_source()
    assert isinstance(source, SimulatorMarketData)


def test_factory_ignores_whitespace_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    source = create_market_data_source()
    assert isinstance(source, SimulatorMarketData)


def test_factory_respects_tick_interval(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.setenv("SIMULATOR_TICK_INTERVAL", "1.0")
    source = create_market_data_source()
    assert isinstance(source, SimulatorMarketData)
    assert source._tick_interval == 1.0


def test_factory_respects_poll_interval(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL", "5.0")
    source = create_market_data_source()
    assert isinstance(source, MassiveMarketData)
    assert source._poll_interval == 5.0
