"""Abstract interface for market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PriceUpdate


class MarketDataSource(ABC):
    """Abstract interface for market data providers.

    Both the simulator and Massive API client implement this interface.
    The rest of the backend (SSE streaming, portfolio pricing, trade
    execution) depends only on this interface.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start producing price updates."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the background task."""

    @abstractmethod
    def register_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Add a ticker to track."""

    @abstractmethod
    def unregister_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker and remove it from the price cache."""

    @abstractmethod
    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent price for a single ticker, or None."""

    @abstractmethod
    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent price for every tracked ticker."""
