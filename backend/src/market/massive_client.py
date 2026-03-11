"""Massive (Polygon.io) market data source -- polls REST API for real prices."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .cache import PriceCache
from .interface import MarketDataSource
from .models import PriceUpdate

logger = logging.getLogger(__name__)

BASE_URL = "https://api.polygon.io"
SNAPSHOTS_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"


class MassiveMarketData(MarketDataSource):
    """Market data source that polls the Massive (Polygon.io) REST API.

    Uses the Snapshots endpoint to fetch current prices for all watched
    tickers in a single API call. Default 15-second poll interval for the
    free tier (5 req/min).
    """

    def __init__(
        self,
        api_key: str,
        poll_interval: float = 15.0,
        request_timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._request_timeout = request_timeout
        self._tickers: set[str] = set()
        self._cache = PriceCache()
        self._task: asyncio.Task | None = None
        self._consecutive_errors = 0

    async def start(self) -> None:
        """Launch the polling loop as a background asyncio task."""
        logger.info(
            "Starting Massive API poller (poll_interval=%.1fs)",
            self._poll_interval,
        )
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Cancel the polling loop and wait for it to finish."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Massive API poller stopped")

    def register_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Add a ticker to the poll set. seed_price is ignored."""
        self._tickers.add(ticker.upper())

    def unregister_ticker(self, ticker: str) -> None:
        """Remove a ticker from the poll set and price cache."""
        ticker_upper = ticker.upper()
        self._tickers.discard(ticker_upper)
        self._cache.remove(ticker_upper)

    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent polled price for a ticker."""
        return self._cache.get(ticker.upper())

    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent polled price for every tracked ticker."""
        return self._cache.get_all()

    async def _poll_loop(self) -> None:
        """Main polling loop -- fetches snapshots and updates the cache."""
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            while True:
                if self._tickers:
                    await self._fetch_and_update(client)
                await asyncio.sleep(self._poll_interval)

    async def _fetch_and_update(self, client: httpx.AsyncClient) -> None:
        """Fetch snapshots for all tracked tickers and update the cache."""
        ticker_str = ",".join(sorted(self._tickers))
        url = f"{BASE_URL}{SNAPSHOTS_PATH}"

        try:
            resp = await client.get(
                url,
                params={"tickers": ticker_str},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()

            data = resp.json()
            now = datetime.now(timezone.utc)
            count = 0

            for t in data.get("tickers", []):
                ticker = t.get("ticker")
                if not ticker:
                    continue
                last_trade = t.get("lastTrade", {})
                price = last_trade.get("p")
                if price is not None:
                    self._cache.update(ticker, float(price), now)
                    count += 1

            self._consecutive_errors = 0
            logger.debug("Massive poll: updated %d/%d tickers", count, len(self._tickers))

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                logger.warning("Massive API rate limited (429). Backing off %.1fs", self._poll_interval)
                await asyncio.sleep(self._poll_interval)
            elif status == 401:
                logger.error("Massive API authentication failed (401). Check MASSIVE_API_KEY.")
            elif status == 403:
                logger.error("Massive API forbidden (403). Endpoint may not be available on your plan.")
            else:
                logger.error("Massive API HTTP error: %d %s", status, e.response.text[:200])
            self._consecutive_errors += 1

        except httpx.RequestError as e:
            self._consecutive_errors += 1
            logger.warning(
                "Massive API request error (attempt %d): %s",
                self._consecutive_errors,
                str(e),
            )
