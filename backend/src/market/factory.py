"""Factory function to create the appropriate market data source."""

from __future__ import annotations

import logging
import os

from .interface import MarketDataSource

logger = logging.getLogger(__name__)


def create_market_data_source() -> MarketDataSource:
    """Create a market data source based on environment configuration.

    If MASSIVE_API_KEY is set and non-empty, returns a MassiveMarketData
    instance. Otherwise, returns a SimulatorMarketData instance.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveMarketData

        poll_interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15.0"))
        logger.info("Using Massive API for market data (poll_interval=%.1fs)", poll_interval)
        return MassiveMarketData(api_key=api_key, poll_interval=poll_interval)
    else:
        from .simulator import SimulatorMarketData

        tick_interval = float(os.environ.get("SIMULATOR_TICK_INTERVAL", "0.5"))
        logger.info("Using simulator for market data (tick_interval=%.1fs)", tick_interval)
        return SimulatorMarketData(tick_interval=tick_interval)
