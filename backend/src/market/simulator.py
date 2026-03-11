"""Simulator market data source -- generates prices using GBM."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .cache import PriceCache
from .engine import SimulationEngine
from .interface import MarketDataSource
from .models import PriceUpdate

logger = logging.getLogger(__name__)


class SimulatorMarketData(MarketDataSource):
    """Market data source that generates simulated prices using GBM.

    Runs a background asyncio task that calls SimulationEngine.tick()
    at the configured interval and writes results to the PriceCache.
    """

    def __init__(
        self,
        tick_interval: float = 0.5,
        seed: int | None = None,
    ) -> None:
        self._tick_interval = tick_interval
        self._cache = PriceCache()
        self._engine = SimulationEngine(tick_interval=tick_interval, seed=seed)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Launch the tick loop as a background asyncio task."""
        logger.info(
            "Starting market simulator (tick_interval=%.1fs)",
            self._tick_interval,
        )
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Cancel the tick loop and wait for it to finish."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Market simulator stopped")

    def register_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Add a ticker to the simulation."""
        self._engine.add_ticker(ticker, seed_price)

    def unregister_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation and price cache."""
        self._engine.remove_ticker(ticker)
        self._cache.remove(ticker.upper())

    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent simulated price for a ticker."""
        return self._cache.get(ticker.upper())

    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent simulated price for every tracked ticker."""
        return self._cache.get_all()

    async def _tick_loop(self) -> None:
        """Main simulation loop -- ticks the engine and updates the cache."""
        while True:
            try:
                updates = self._engine.tick()
                now = datetime.now(timezone.utc)
                for ticker, price in updates.items():
                    self._cache.update(ticker, price, now)
            except Exception:
                logger.exception("Error in simulator tick")
            await asyncio.sleep(self._tick_interval)
