"""Thread-safe in-memory price cache."""

from __future__ import annotations

import threading
from datetime import datetime

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of the latest price per ticker.

    The market data source (simulator or Massive client) writes here.
    The SSE endpoint reads from here. Direction (up/down/unchanged) is
    computed at write time by comparing against the previous price.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = threading.Lock()

    def update(self, ticker: str, price: float, timestamp: datetime) -> PriceUpdate:
        """Update the cache with a new price and return the resulting PriceUpdate.

        The direction field is computed by comparing against the previously
        cached price. If there is no previous entry (first update for this
        ticker), prev_price equals price and direction is "unchanged".
        """
        with self._lock:
            prev = self._prices.get(ticker)
            prev_price = prev.price if prev else price

            if price > prev_price:
                direction = "up"
            elif price < prev_price:
                direction = "down"
            else:
                direction = "unchanged"

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                prev_price=round(prev_price, 2),
                timestamp=timestamp,
                direction=direction,
            )
            self._prices[ticker] = update
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Get the latest price for a single ticker, or None if not tracked."""
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        """Get the latest price for every tracked ticker."""
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        """Remove a ticker from the cache (called when unregistering)."""
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def tickers(self) -> list[str]:
        """List of currently cached tickers."""
        with self._lock:
            return list(self._prices.keys())
