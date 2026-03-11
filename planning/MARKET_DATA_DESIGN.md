# Market Data Backend — Detailed Implementation Design

This document provides a complete, implementation-ready design for the FinAlly market data subsystem. It covers the unified interface, price cache, GBM simulator, Massive API client, SSE streaming endpoint, FastAPI integration, and testing strategy — with full code snippets for every module.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Core Data Model — `models.py`](#3-core-data-model)
4. [Price Cache — `cache.py`](#4-price-cache)
5. [Abstract Interface — `interface.py`](#5-abstract-interface)
6. [Seed Prices & Ticker Profiles — `seed_prices.py`](#6-seed-prices--ticker-profiles)
7. [Simulation Engine — `engine.py`](#7-simulation-engine)
8. [Simulator Implementation — `simulator.py`](#8-simulator-implementation)
9. [Massive API Client — `massive_client.py`](#9-massive-api-client)
10. [Factory — `factory.py`](#10-factory)
11. [SSE Streaming Endpoint — `sse.py`](#11-sse-streaming-endpoint)
12. [FastAPI Lifespan Integration](#12-fastapi-lifespan-integration)
13. [Watchlist Integration](#13-watchlist-integration)
14. [Error Handling & Resilience](#14-error-handling--resilience)
15. [Testing Strategy](#15-testing-strategy)
16. [Configuration Reference](#16-configuration-reference)

---

## 1. Architecture Overview

The market data subsystem is a self-contained module within the backend. It has one job: produce `PriceUpdate` objects for every tracked ticker at a regular cadence and make them available to the SSE endpoint.

```
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Application                                         │
│                                                              │
│  ┌─────────────┐    lifespan     ┌──────────────────────┐   │
│  │  factory.py  │───creates──────▶│  MarketDataSource    │   │
│  │              │                 │  (Simulator OR        │   │
│  │              │                 │   MassiveMarketData)  │   │
│  └─────────────┘                 └──────────┬───────────┘   │
│                                              │               │
│                                     writes to│               │
│                                              ▼               │
│                                    ┌─────────────────┐       │
│                                    │   PriceCache     │       │
│                                    │  (in-memory,     │       │
│                                    │   thread-safe)   │       │
│                                    └────────┬────────┘       │
│                                             │                │
│                                    reads from│                │
│                                             ▼                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  GET /api/stream/prices  (SSE endpoint)             │    │
│  │  Pushes PriceUpdate JSON every ~500ms               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Watchlist API  (POST/DELETE /api/watchlist)         │    │
│  │  Calls register_ticker / unregister_ticker          │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

**Key design principles:**
- **One interface, two implementations** — all downstream code is source-agnostic
- **Push-based ticker registration** — watchlist API notifies the source directly, no DB polling per tick
- **In-memory price cache** — single source of truth for latest prices, thread-safe
- **Background asyncio task** — simulator ticks or Massive polls in a long-running coroutine

---

## 2. File Structure

```
backend/
  src/
    market/
      __init__.py              # Public exports: MarketDataSource, PriceUpdate, PriceCache, create_market_data_source
      models.py                # PriceUpdate dataclass
      cache.py                 # PriceCache (thread-safe in-memory store)
      interface.py             # MarketDataSource ABC
      factory.py               # create_market_data_source() factory function
      simulator.py             # SimulatorMarketData (MarketDataSource impl)
      engine.py                # SimulationEngine (GBM math, correlation, events)
      seed_prices.py           # SEED_PRICES dict, TICKER_PROFILES, DEFAULT_SEED_RANGE
      massive_client.py        # MassiveMarketData (MarketDataSource impl)
      sse.py                   # SSE streaming endpoint (FastAPI route)
```

Every file is small and focused. No file exceeds ~150 lines. The `__init__.py` re-exports the public API so consumers import from `market` directly.

---

## 3. Core Data Model

**File: `backend/src/market/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """A single price update for one ticker.

    This is the universal output format. Both the simulator and Massive client
    produce PriceUpdate objects. The SSE stream serializes these to JSON.
    """

    ticker: str
    price: float
    prev_price: float
    timestamp: datetime
    direction: str  # "up", "down", or "unchanged"

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON encoding in the SSE stream."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.prev_price,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
        }
```

**Design decisions:**
- `frozen=True` — price updates are immutable value objects; prevents accidental mutation
- `slots=True` — memory-efficient since we create many of these per second
- `to_dict()` — convenience method so the SSE endpoint doesn't need to know about field names

---

## 4. Price Cache

**File: `backend/src/market/cache.py`**

The price cache is the central data store that bridges the market data source (producer) and the SSE endpoint (consumer). It must be thread-safe because the simulator/poller runs in an asyncio task while the SSE endpoint reads concurrently.

```python
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
        """Get the latest price for every tracked ticker.

        Returns a shallow copy of the internal dict so callers can iterate
        without holding the lock.
        """
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
```

**Why `threading.Lock` instead of `asyncio.Lock`?**
- The cache is shared between asyncio coroutines and potentially thread-pool executors
- `threading.Lock` is safe in both contexts; `asyncio.Lock` only works within a single event loop
- Lock contention is negligible — each critical section is a dict lookup/write (~microseconds)

---

## 5. Abstract Interface

**File: `backend/src/market/interface.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PriceUpdate


class MarketDataSource(ABC):
    """Abstract interface for market data providers.

    Both the simulator and Massive API client implement this interface.
    The rest of the backend (SSE streaming, portfolio pricing, trade
    execution) depends only on this interface — never on a concrete
    implementation.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start producing price updates.

        For the simulator: launches the GBM tick loop as an asyncio task.
        For Massive: launches the REST polling loop as an asyncio task.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the background task.

        Cancels the running asyncio task and awaits its completion.
        """

    @abstractmethod
    def register_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Add a ticker to track.

        For the simulator: seed_price sets the starting price (falls back to
        the seed price lookup table, then to a random price in $50-$300).
        For Massive: seed_price is ignored — real price comes on next poll.

        This is called by the watchlist API when a ticker is added.
        The ticker appears in the SSE stream on the next tick/poll cycle.
        """

    @abstractmethod
    def unregister_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker.

        Removes it from the internal state and the price cache.
        Called by the watchlist API when a ticker is removed.
        """

    @abstractmethod
    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent price for a single ticker, or None."""

    @abstractmethod
    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent price for every tracked ticker."""
```

**Contract guarantees:**
- After `start()`, the source produces price updates at its configured cadence
- After `register_ticker()`, the ticker appears in `get_all_latest()` on the next tick
- After `unregister_ticker()`, the ticker is immediately removed from `get_all_latest()`
- `stop()` is idempotent — safe to call multiple times

---

## 6. Seed Prices & Ticker Profiles

**File: `backend/src/market/seed_prices.py`**

```python
"""Seed prices and GBM parameters for the market simulator.

Seed prices are realistic approximations for the default watchlist tickers.
Ticker profiles define per-stock drift (mu), volatility (sigma), and sector
grouping for correlated moves.
"""

from __future__ import annotations

# Realistic seed prices for the default watchlist (as of project inception)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 130.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 650.00,
}

# For tickers not in the seed table, assign a random price in this range
DEFAULT_SEED_RANGE: tuple[float, float] = (50.0, 300.0)

# GBM parameters per ticker
# mu = annualized drift (expected return), sigma = annualized volatility
# sector = grouping key for correlated moves
TICKER_PROFILES: dict[str, dict] = {
    "AAPL":  {"mu": 0.10, "sigma": 0.22, "sector": "tech"},
    "GOOGL": {"mu": 0.08, "sigma": 0.25, "sector": "tech"},
    "MSFT":  {"mu": 0.10, "sigma": 0.20, "sector": "tech"},
    "AMZN":  {"mu": 0.12, "sigma": 0.28, "sector": "tech"},
    "TSLA":  {"mu": 0.15, "sigma": 0.50, "sector": "auto"},
    "NVDA":  {"mu": 0.15, "sigma": 0.40, "sector": "tech"},
    "META":  {"mu": 0.10, "sigma": 0.30, "sector": "tech"},
    "JPM":   {"mu": 0.06, "sigma": 0.18, "sector": "finance"},
    "V":     {"mu": 0.08, "sigma": 0.16, "sector": "finance"},
    "NFLX":  {"mu": 0.12, "sigma": 0.35, "sector": "media"},
}

# Defaults for tickers not in TICKER_PROFILES
DEFAULT_MU = 0.08
DEFAULT_SIGMA = 0.25
DEFAULT_SECTOR = "other"
```

---

## 7. Simulation Engine

**File: `backend/src/market/engine.py`**

The simulation engine is the mathematical core. It uses Geometric Brownian Motion with correlated sector-level shocks and occasional random events for visual drama.

```python
"""GBM-based price simulation engine with correlated moves and random events."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from .seed_prices import (
    DEFAULT_MU,
    DEFAULT_SECTOR,
    DEFAULT_SEED_RANGE,
    DEFAULT_SIGMA,
    SEED_PRICES,
    TICKER_PROFILES,
)


@dataclass
class TickerParams:
    """Mutable state and parameters for one simulated ticker."""

    price: float          # Current price (mutated each tick)
    mu: float             # Annualized drift
    sigma: float          # Annualized volatility
    sector: str           # Sector grouping key for correlation


# Correlation coefficient for tickers within the same sector.
# 0.6 means ~60% of each tick's move is shared with sector peers.
INTRA_SECTOR_CORRELATION = 0.6

# Random events: 2% chance per tick, 2-5% magnitude
EVENT_PROBABILITY = 0.02
EVENT_MIN_MAGNITUDE = 0.02
EVENT_MAX_MAGNITUDE = 0.05

# Minimum price floor to prevent zero/negative prices
MIN_PRICE = 0.01


class SimulationEngine:
    """Generates correlated GBM price updates for all registered tickers.

    Each call to tick() advances every ticker by one time step and returns
    a dict of {ticker: new_price}. The engine is deterministic given the
    same random seed (useful for testing).

    GBM formula (discrete):
        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)

    Correlation model:
        Z_ticker = rho * Z_sector + sqrt(1 - rho^2) * Z_individual
    """

    def __init__(
        self,
        tick_interval: float = 0.5,
        seed: int | None = None,
    ) -> None:
        self._tickers: dict[str, TickerParams] = {}
        # Convert tick interval (seconds) to fraction of a trading year.
        # 252 trading days × 6.5 hours/day × 3600 seconds/hour = 5,896,800 seconds
        self._dt = tick_interval / (252 * 6.5 * 3600)
        self._rng = random.Random(seed)

    def add_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Register a ticker for simulation.

        Args:
            ticker: Stock symbol (uppercased internally).
            seed_price: Starting price. Falls back to SEED_PRICES lookup,
                        then to a random value in DEFAULT_SEED_RANGE.
        """
        ticker = ticker.upper()
        if ticker in self._tickers:
            return  # Already tracking — no-op

        profile = TICKER_PROFILES.get(ticker, {
            "mu": DEFAULT_MU,
            "sigma": DEFAULT_SIGMA,
            "sector": DEFAULT_SECTOR,
        })

        price = seed_price or SEED_PRICES.get(ticker)
        if price is None:
            price = self._rng.uniform(*DEFAULT_SEED_RANGE)

        self._tickers[ticker] = TickerParams(
            price=price,
            mu=profile["mu"],
            sigma=profile["sigma"],
            sector=profile["sector"],
        )

    def remove_ticker(self, ticker: str) -> None:
        """Unregister a ticker from simulation."""
        self._tickers.pop(ticker.upper(), None)

    def tick(self) -> dict[str, float]:
        """Advance all tickers by one time step.

        Returns:
            Dict mapping ticker symbol to new price (rounded to 2 decimals).
            Empty dict if no tickers are registered.
        """
        if not self._tickers:
            return {}

        # 1. Group tickers by sector
        sectors: dict[str, list[str]] = defaultdict(list)
        for ticker, params in self._tickers.items():
            sectors[params.sector].append(ticker)

        # 2. Generate one shared random shock per sector
        sector_shocks: dict[str, float] = {
            sector: self._rng.gauss(0, 1) for sector in sectors
        }

        # 3. Determine if a random event fires this tick
        event_ticker: str | None = None
        event_shock: float = 0.0
        if self._rng.random() < EVENT_PROBABILITY and self._tickers:
            event_ticker = self._rng.choice(list(self._tickers.keys()))
            magnitude = self._rng.uniform(EVENT_MIN_MAGNITUDE, EVENT_MAX_MAGNITUDE)
            event_shock = magnitude if self._rng.random() > 0.5 else -magnitude

        # 4. Apply GBM to each ticker
        rho = INTRA_SECTOR_CORRELATION
        rho_complement = math.sqrt(1 - rho ** 2)
        results: dict[str, float] = {}

        for ticker, params in self._tickers.items():
            z_sector = sector_shocks[params.sector]
            z_individual = self._rng.gauss(0, 1)
            z = rho * z_sector + rho_complement * z_individual

            # GBM step: S(t+dt) = S(t) * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)
            drift = (params.mu - 0.5 * params.sigma ** 2) * self._dt
            diffusion = params.sigma * math.sqrt(self._dt) * z
            new_price = params.price * math.exp(drift + diffusion)

            # Apply event shock if this ticker was selected
            if ticker == event_ticker:
                new_price *= (1 + event_shock)

            # Floor at MIN_PRICE to prevent zero/negative
            new_price = max(new_price, MIN_PRICE)

            # Update mutable state
            params.price = new_price
            results[ticker] = round(new_price, 2)

        return results

    @property
    def tracked_tickers(self) -> list[str]:
        """List of currently tracked ticker symbols."""
        return list(self._tickers.keys())

    def get_current_price(self, ticker: str) -> float | None:
        """Get the current simulated price for a ticker, or None."""
        params = self._tickers.get(ticker.upper())
        return round(params.price, 2) if params else None
```

### GBM Math Explained

The discrete-time GBM step is:

```
S(t+dt) = S(t) × exp((μ − σ²/2) × dt + σ × √dt × Z)
```

| Symbol | Meaning | Example |
|--------|---------|---------|
| `S(t)` | Current price | $190.00 |
| `μ` | Annualized drift | 0.10 (10% annual) |
| `σ` | Annualized volatility | 0.22 (22%) |
| `dt` | Time step (fraction of year) | ~8.48×10⁻⁸ for 500ms ticks |
| `Z` | Correlated standard normal | ~N(0,1) with sector correlation |

**Time step derivation:**
```
dt = tick_interval_seconds / (252 × 6.5 × 3600)
   = 0.5 / 5,896,800
   ≈ 8.48 × 10⁻⁸
```

This keeps per-tick moves tiny and realistic. Over a full simulated trading day (~46,800 ticks at 500ms), cumulative drift and volatility approximate real daily ranges.

### Correlation Model

To make same-sector stocks move together:

```
Z_ticker = ρ × Z_sector + √(1 − ρ²) × Z_individual
```

With `ρ = 0.6`, about 60% of each ticker's move comes from its sector's shared shock and 40% from its individual randomness. This means when AAPL drops, MSFT and NVDA tend to drop too — creating a realistic feel.

### Random Events

Every tick has a 2% chance of triggering a "news event" on one random ticker:
- One ticker is randomly selected
- A 2–5% sudden move (equally likely up or down) is applied as a multiplicative shock
- This creates visible spikes in sparklines and price flashes — visual drama for the demo

At 500ms ticks, events fire roughly once every 25 seconds.

---

## 8. Simulator Implementation

**File: `backend/src/market/simulator.py`**

```python
"""Simulator market data source — generates prices using GBM."""

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
        """Add a ticker to the simulation.

        The ticker will appear in the next tick cycle. If seed_price is
        provided it sets the starting price; otherwise the engine falls
        back to the built-in seed price table.
        """
        self._engine.add_ticker(ticker, seed_price)
        logger.debug("Registered ticker %s (seed_price=%s)", ticker, seed_price)

    def unregister_ticker(self, ticker: str) -> None:
        """Remove a ticker from the simulation and price cache."""
        self._engine.remove_ticker(ticker)
        self._cache.remove(ticker.upper())
        logger.debug("Unregistered ticker %s", ticker)

    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent simulated price for a ticker."""
        return self._cache.get(ticker.upper())

    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent simulated price for every tracked ticker."""
        return self._cache.get_all()

    async def _tick_loop(self) -> None:
        """Main simulation loop — ticks the engine and updates the cache."""
        logger.info("Simulator tick loop started")
        while True:
            try:
                updates = self._engine.tick()
                now = datetime.now(timezone.utc)
                for ticker, price in updates.items():
                    self._cache.update(ticker, price, now)
            except Exception:
                logger.exception("Error in simulator tick")
            await asyncio.sleep(self._tick_interval)
```

**Usage example:**

```python
sim = SimulatorMarketData(tick_interval=0.5)

# Register the default watchlist
for ticker in ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]:
    sim.register_ticker(ticker)

await sim.start()

# Later, read prices
aapl = sim.get_latest("AAPL")
# PriceUpdate(ticker='AAPL', price=190.12, prev_price=190.00, timestamp=..., direction='up')

all_prices = sim.get_all_latest()
# {'AAPL': PriceUpdate(...), 'GOOGL': PriceUpdate(...), ...}

# Add a new ticker dynamically
sim.register_ticker("PYPL")  # Gets random seed price since not in lookup table

# Shut down
await sim.stop()
```

---

## 9. Massive API Client

**File: `backend/src/market/massive_client.py`**

```python
"""Massive (Polygon.io) market data source — polls REST API for real prices."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .cache import PriceCache
from .interface import MarketDataSource
from .models import PriceUpdate

logger = logging.getLogger(__name__)

# Polygon.io rebranded to Massive; legacy domain still works
BASE_URL = "https://api.polygon.io"
SNAPSHOTS_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"


class MassiveMarketData(MarketDataSource):
    """Market data source that polls the Massive (Polygon.io) REST API.

    Uses the Snapshots endpoint to fetch current prices for all watched
    tickers in a single API call. Designed for the free tier (5 req/min)
    with a default 15-second poll interval.
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
        """Add a ticker to the poll set.

        seed_price is ignored — the real price is fetched on the next poll.
        The ticker is included in the next API call automatically.
        """
        self._tickers.add(ticker.upper())
        logger.debug("Registered ticker %s for Massive polling", ticker)

    def unregister_ticker(self, ticker: str) -> None:
        """Remove a ticker from the poll set and price cache."""
        ticker_upper = ticker.upper()
        self._tickers.discard(ticker_upper)
        self._cache.remove(ticker_upper)
        logger.debug("Unregistered ticker %s from Massive polling", ticker)

    def get_latest(self, ticker: str) -> PriceUpdate | None:
        """Get the most recent polled price for a ticker."""
        return self._cache.get(ticker.upper())

    def get_all_latest(self) -> dict[str, PriceUpdate]:
        """Get the most recent polled price for every tracked ticker."""
        return self._cache.get_all()

    async def _poll_loop(self) -> None:
        """Main polling loop — fetches snapshots and updates the cache."""
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            while True:
                if self._tickers:
                    await self._fetch_and_update(client)
                await asyncio.sleep(self._poll_interval)

    async def _fetch_and_update(self, client: httpx.AsyncClient) -> None:
        """Fetch snapshots for all tracked tickers and update the cache.

        Handles rate limiting (429) with backoff and logs errors without
        crashing the polling loop.
        """
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

                # Extract price from lastTrade.p (most recent trade price)
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
                # Rate limited — back off for one extra interval
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
            # Network error (DNS, timeout, connection refused, etc.)
            self._consecutive_errors += 1
            logger.warning(
                "Massive API request error (attempt %d): %s",
                self._consecutive_errors,
                str(e),
            )
```

### Massive API Response Parsing

The snapshot endpoint returns nested JSON. Here's exactly what we extract:

```json
{
  "tickers": [
    {
      "ticker": "AAPL",
      "lastTrade": {
        "p": 191.25       // <-- THIS is the current price we use
      },
      "prevDay": {
        "c": 190.00       // Previous day close (available for future use)
      },
      "todaysChange": 1.25,      // Available for daily change display
      "todaysChangePerc": 0.65   // Available for daily change % display
    }
  ]
}
```

We only extract `lastTrade.p` for the price cache. Additional fields (`prevDay.c`, `todaysChange`, `todaysChangePerc`) are available in the response if needed by future features but are not stored in the current cache model.

### Poll Interval Guidance

| Massive Tier | Rate Limit | Recommended `poll_interval` |
|---|---|---|
| Free | 5 req/min | `15.0` (default) |
| Starter | ~100 req/sec soft cap | `5.0` |
| Developer+ | ~100 req/sec soft cap | `2.0` |

Set via environment variable or constructor parameter. The default of 15 seconds stays safely within the free tier's 5 requests/minute limit.

---

## 10. Factory

**File: `backend/src/market/factory.py`**

```python
"""Factory function to create the appropriate market data source."""

from __future__ import annotations

import logging
import os

from .interface import MarketDataSource

logger = logging.getLogger(__name__)


def create_market_data_source() -> MarketDataSource:
    """Create a market data source based on environment configuration.

    If MASSIVE_API_KEY is set and non-empty, returns a MassiveMarketData
    instance that polls the real Massive/Polygon.io API.

    Otherwise, returns a SimulatorMarketData instance that generates
    prices using GBM (no external dependencies).
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
```

**Why lazy imports?** — The `from .massive_client import ...` import is inside the `if` branch so that `httpx` (a Massive-only dependency) is not imported when running the simulator. This keeps the simulator zero-dependency (stdlib only).

---

## 11. SSE Streaming Endpoint

**File: `backend/src/market/sse.py`**

```python
"""Server-Sent Events endpoint for streaming live price updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .interface import MarketDataSource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/stream/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    """SSE endpoint that pushes price updates for all tracked tickers.

    The client connects with EventSource and receives a stream of JSON
    events at ~500ms intervals. Each event contains one ticker's price
    update. All tracked tickers are sent each cycle.

    Event format:
        data: {"ticker":"AAPL","price":191.25,"prev_price":190.80,"timestamp":"...","direction":"up"}

    The connection stays open until the client disconnects. EventSource
    handles reconnection automatically with built-in retry.
    """
    source: MarketDataSource = request.app.state.market_data

    async def event_generator():
        # Send retry directive so EventSource reconnects after 1s on disconnect
        yield "retry: 1000\n\n"

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                break

            # Get all current prices and emit one event per ticker
            updates = source.get_all_latest()
            for ticker, update in updates.items():
                data = json.dumps(update.to_dict())
                yield f"data: {data}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if behind a proxy
        },
    )
```

### SSE Protocol Details

Each SSE event follows the standard format:
```
data: {"ticker":"AAPL","price":191.25,"prev_price":190.80,"timestamp":"2025-01-15T14:30:00Z","direction":"up"}

data: {"ticker":"GOOGL","price":175.42,"prev_price":175.30,"timestamp":"2025-01-15T14:30:00Z","direction":"up"}

```

- Each `data:` line is one event
- Events are separated by a blank line (`\n\n`)
- The `retry: 1000` directive tells the browser to reconnect after 1 second if the connection drops
- Response headers disable caching and proxy buffering

### Client-Side Usage (Frontend Reference)

```typescript
const eventSource = new EventSource('/api/stream/prices');

eventSource.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // { ticker: "AAPL", price: 191.25, prev_price: 190.80, timestamp: "...", direction: "up" }
  handlePriceUpdate(update);
};

eventSource.onerror = () => {
  // EventSource automatically reconnects (after retry interval)
  updateConnectionStatus('reconnecting');
};
```

---

## 12. FastAPI Lifespan Integration

The market data source is created and started in the FastAPI lifespan context manager, ensuring clean startup and shutdown.

```python
"""FastAPI application lifespan — starts/stops the market data source."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from market.factory import create_market_data_source
from market.sse import router as sse_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize market data on startup, clean up on shutdown."""

    # 1. Create the appropriate market data source (simulator or Massive)
    source = create_market_data_source()

    # 2. Register seed tickers from the database
    #    (This function is provided by the database module — reads the watchlist table)
    watchlist_tickers = await get_watchlist_tickers_from_db()
    for ticker in watchlist_tickers:
        source.register_ticker(ticker)

    # 3. Start the background task (tick loop or poll loop)
    await source.start()

    # 4. Store on app.state so routes can access it
    app.state.market_data = source

    yield  # Application is running

    # 5. Graceful shutdown
    await source.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(sse_router)
```

### Accessing the Market Data Source from Any Route

Any route handler can access the market data source via `request.app.state.market_data`:

```python
from fastapi import Request

@router.get("/api/portfolio")
async def get_portfolio(request: Request):
    source = request.app.state.market_data

    # Get current price for P&L calculation
    aapl_price = source.get_latest("AAPL")
    if aapl_price:
        current_price = aapl_price.price
    # ...
```

---

## 13. Watchlist Integration

The watchlist API calls `register_ticker` / `unregister_ticker` directly on the market data source. This push-based approach ensures new tickers appear in the SSE stream immediately without any DB polling per tick.

```python
"""Watchlist route handlers — integrated with market data source."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class AddTickerRequest(BaseModel):
    ticker: str


@router.post("/api/watchlist")
async def add_to_watchlist(request: Request, body: AddTickerRequest):
    ticker = body.ticker.upper().strip()

    if not ticker or not ticker.isalpha():
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    # 1. Insert into database (raises 409 if duplicate)
    try:
        await add_ticker_to_db(ticker, user_id="default")
    except DuplicateTickerError:
        raise HTTPException(status_code=409, detail=f"{ticker} is already in the watchlist")

    # 2. Notify market data source to start tracking
    source = request.app.state.market_data
    source.register_ticker(ticker)

    return {"ticker": ticker, "status": "added"}


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(request: Request, ticker: str):
    ticker = ticker.upper().strip()

    # 1. Remove from database
    removed = await remove_ticker_from_db(ticker, user_id="default")
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} is not in the watchlist")

    # 2. Notify market data source to stop tracking
    source = request.app.state.market_data
    source.unregister_ticker(ticker)

    return {"ticker": ticker, "status": "removed"}


@router.get("/api/watchlist")
async def get_watchlist(request: Request):
    """Return the watchlist with current prices from the market data source."""
    tickers = await get_watchlist_from_db(user_id="default")
    source = request.app.state.market_data

    result = []
    for entry in tickers:
        update = source.get_latest(entry["ticker"])
        result.append({
            "ticker": entry["ticker"],
            "added_at": entry["added_at"],
            "price": update.price if update else None,
            "prev_price": update.prev_price if update else None,
            "direction": update.direction if update else None,
        })

    return {"watchlist": result}
```

### Data Flow: Adding a Ticker

```
User clicks "Add PYPL"
    │
    ▼
POST /api/watchlist  {ticker: "PYPL"}
    │
    ├── 1. INSERT INTO watchlist (ticker="PYPL", user_id="default")
    │
    ├── 2. source.register_ticker("PYPL")
    │       │
    │       ├── Simulator: engine.add_ticker("PYPL", None)
    │       │   → assigns random seed price ($50-$300)
    │       │   → starts generating GBM prices on next tick
    │       │
    │       └── Massive: self._tickers.add("PYPL")
    │           → included in next API poll (~15s)
    │
    └── 3. Return {ticker: "PYPL", status: "added"}

Next tick/poll:
    PYPL appears in source.get_all_latest()
    → SSE pushes PYPL price to frontend
    → Watchlist UI shows PYPL with live price
```

---

## 14. Error Handling & Resilience

### Simulator Resilience

The simulator is pure Python with no external dependencies, so failures are minimal:

| Scenario | Handling |
|---|---|
| Exception in `tick()` | Caught and logged; loop continues on next tick |
| `asyncio.CancelledError` | Propagated cleanly; stops the loop |
| Price drops to 0 | Clamped to `MIN_PRICE` (0.01) |
| Unknown ticker registered | Assigned random seed price and default GBM params |

### Massive Client Resilience

The Massive client handles network and API errors gracefully:

| Scenario | Handling |
|---|---|
| HTTP 429 (rate limited) | Log warning, sleep one extra poll interval, retry next cycle |
| HTTP 401 (bad API key) | Log error, continue polling (may recover if key is fixed at runtime) |
| HTTP 403 (plan restriction) | Log error, continue polling |
| Network timeout | Log warning, skip this cycle, retry next interval |
| DNS failure | Log warning, skip this cycle, retry next interval |
| Malformed JSON response | Exception caught by outer handler, logged, skip cycle |
| Partial response (some tickers missing) | Update only the tickers present; others keep stale prices |

### SSE Endpoint Resilience

| Scenario | Handling |
|---|---|
| Client disconnects | `request.is_disconnected()` check breaks the loop cleanly |
| No tickers registered | Empty update set — no events pushed, but connection stays open |
| Backend restarts | Client's `EventSource` automatically reconnects after `retry` interval |

---

## 15. Testing Strategy

### Unit Tests for SimulationEngine

```python
"""Tests for the GBM simulation engine."""

import pytest
from market.engine import SimulationEngine


class TestSimulationEngine:
    def test_add_ticker_with_seed_price(self):
        engine = SimulationEngine(seed=42)
        engine.add_ticker("TEST", seed_price=100.0)
        result = engine.tick()
        assert "TEST" in result
        assert result["TEST"] > 0  # Price is positive

    def test_add_ticker_uses_lookup_table(self):
        engine = SimulationEngine(seed=42)
        engine.add_ticker("AAPL")  # In SEED_PRICES at $190
        result = engine.tick()
        # First tick should be close to seed price
        assert 180 < result["AAPL"] < 200

    def test_add_unknown_ticker_gets_random_seed(self):
        engine = SimulationEngine(seed=42)
        engine.add_ticker("ZZZZ")  # Not in lookup table
        result = engine.tick()
        assert 0.01 <= result["ZZZZ"] <= 500  # Within reasonable range

    def test_remove_ticker(self):
        engine = SimulationEngine(seed=42)
        engine.add_ticker("AAPL")
        engine.remove_ticker("AAPL")
        result = engine.tick()
        assert "AAPL" not in result

    def test_tick_empty_returns_empty(self):
        engine = SimulationEngine(seed=42)
        assert engine.tick() == {}

    def test_prices_stay_positive(self):
        """Run many ticks to verify prices never go negative."""
        engine = SimulationEngine(seed=42)
        engine.add_ticker("VOLATILE", seed_price=1.0)
        for _ in range(10_000):
            result = engine.tick()
            assert result["VOLATILE"] >= 0.01

    def test_deterministic_with_seed(self):
        """Same seed produces same sequence of prices."""
        engine1 = SimulationEngine(seed=123)
        engine2 = SimulationEngine(seed=123)
        engine1.add_ticker("AAPL")
        engine2.add_ticker("AAPL")
        for _ in range(100):
            assert engine1.tick() == engine2.tick()

    def test_sector_correlation(self):
        """Tickers in the same sector should have correlated moves."""
        # Run many ticks and check correlation of log-returns
        import math
        engine = SimulationEngine(seed=42)
        engine.add_ticker("AAPL")  # tech
        engine.add_ticker("MSFT")  # tech
        engine.add_ticker("JPM")   # finance

        prices = {"AAPL": [], "MSFT": [], "JPM": []}
        for _ in range(1000):
            result = engine.tick()
            for t in prices:
                prices[t].append(result[t])

        # Compute log-returns
        def log_returns(p):
            return [math.log(p[i] / p[i - 1]) for i in range(1, len(p))]

        aapl_ret = log_returns(prices["AAPL"])
        msft_ret = log_returns(prices["MSFT"])
        jpm_ret = log_returns(prices["JPM"])

        # Compute correlation (simplified)
        def corr(a, b):
            n = len(a)
            mean_a, mean_b = sum(a) / n, sum(b) / n
            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
            std_a = (sum((x - mean_a) ** 2 for x in a) / n) ** 0.5
            std_b = (sum((x - mean_b) ** 2 for x in b) / n) ** 0.5
            return cov / (std_a * std_b) if std_a and std_b else 0

        # Same-sector correlation should be notably higher than cross-sector
        tech_corr = corr(aapl_ret, msft_ret)
        cross_corr = corr(aapl_ret, jpm_ret)
        assert tech_corr > cross_corr
```

### Unit Tests for PriceCache

```python
"""Tests for the thread-safe price cache."""

import pytest
from datetime import datetime, timezone
from market.cache import PriceCache


class TestPriceCache:
    def test_first_update_direction_unchanged(self):
        cache = PriceCache()
        now = datetime.now(timezone.utc)
        update = cache.update("AAPL", 190.0, now)
        assert update.direction == "unchanged"
        assert update.prev_price == 190.0

    def test_price_up(self):
        cache = PriceCache()
        now = datetime.now(timezone.utc)
        cache.update("AAPL", 190.0, now)
        update = cache.update("AAPL", 191.0, now)
        assert update.direction == "up"
        assert update.prev_price == 190.0

    def test_price_down(self):
        cache = PriceCache()
        now = datetime.now(timezone.utc)
        cache.update("AAPL", 190.0, now)
        update = cache.update("AAPL", 189.0, now)
        assert update.direction == "down"

    def test_get_nonexistent_returns_none(self):
        cache = PriceCache()
        assert cache.get("ZZZZ") is None

    def test_get_all_returns_copy(self):
        cache = PriceCache()
        now = datetime.now(timezone.utc)
        cache.update("AAPL", 190.0, now)
        all_prices = cache.get_all()
        assert "AAPL" in all_prices
        # Modifying returned dict doesn't affect cache
        del all_prices["AAPL"]
        assert cache.get("AAPL") is not None

    def test_remove(self):
        cache = PriceCache()
        now = datetime.now(timezone.utc)
        cache.update("AAPL", 190.0, now)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None

    def test_remove_nonexistent_is_noop(self):
        cache = PriceCache()
        cache.remove("ZZZZ")  # Should not raise
```

### Unit Tests for Massive Response Parsing

```python
"""Tests for Massive API response parsing."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
import httpx

from market.massive_client import MassiveMarketData


class TestMassiveResponseParsing:
    @pytest.mark.asyncio
    async def test_parse_valid_snapshot(self):
        """Verify correct extraction of lastTrade.p from snapshot response."""
        mock_response = {
            "count": 2,
            "status": "OK",
            "tickers": [
                {
                    "ticker": "AAPL",
                    "lastTrade": {"p": 191.25, "s": 100, "t": 1617827221349730300},
                    "prevDay": {"c": 190.00},
                    "todaysChange": 1.25,
                    "todaysChangePerc": 0.65,
                },
                {
                    "ticker": "GOOGL",
                    "lastTrade": {"p": 175.42, "s": 50, "t": 1617827221349730300},
                    "prevDay": {"c": 174.80},
                    "todaysChange": 0.62,
                    "todaysChangePerc": 0.35,
                },
            ],
        }

        client = MassiveMarketData(api_key="test-key")
        client.register_ticker("AAPL")
        client.register_ticker("GOOGL")

        # Mock httpx response
        mock_http_response = AsyncMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = lambda: None

        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_http_response

        await client._fetch_and_update(mock_http_client)

        aapl = client.get_latest("AAPL")
        assert aapl is not None
        assert aapl.price == 191.25

        googl = client.get_latest("GOOGL")
        assert googl is not None
        assert googl.price == 175.42

    @pytest.mark.asyncio
    async def test_handle_missing_last_trade(self):
        """Tickers without lastTrade.p should be skipped, not crash."""
        mock_response = {
            "tickers": [
                {"ticker": "AAPL", "lastTrade": {}},  # No 'p' field
            ],
        }

        client = MassiveMarketData(api_key="test-key")
        client.register_ticker("AAPL")

        mock_http_response = AsyncMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = lambda: None

        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_http_response

        await client._fetch_and_update(mock_http_client)

        assert client.get_latest("AAPL") is None  # Not updated

    @pytest.mark.asyncio
    async def test_handle_empty_tickers_list(self):
        """Empty tickers array should not crash."""
        mock_response = {"tickers": []}

        client = MassiveMarketData(api_key="test-key")
        client.register_ticker("AAPL")

        mock_http_response = AsyncMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response
        mock_http_response.raise_for_status = lambda: None

        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_http_response

        await client._fetch_and_update(mock_http_client)

        assert client.get_latest("AAPL") is None
```

### Integration Test: Interface Conformance

```python
"""Verify both implementations conform to the MarketDataSource interface."""

import pytest
import asyncio
from market.simulator import SimulatorMarketData
from market.massive_client import MassiveMarketData
from market.interface import MarketDataSource


@pytest.fixture
def simulator():
    return SimulatorMarketData(tick_interval=0.1, seed=42)


@pytest.fixture
def massive_client():
    return MassiveMarketData(api_key="test-key", poll_interval=0.1)


@pytest.mark.parametrize("source_fixture", ["simulator", "massive_client"])
class TestMarketDataSourceInterface:
    """Tests that apply to both implementations."""

    def test_is_market_data_source(self, source_fixture, request):
        source = request.getfixturevalue(source_fixture)
        assert isinstance(source, MarketDataSource)

    def test_register_and_unregister(self, source_fixture, request):
        source = request.getfixturevalue(source_fixture)
        source.register_ticker("AAPL")
        source.unregister_ticker("AAPL")
        assert source.get_latest("AAPL") is None

    def test_get_latest_unknown_returns_none(self, source_fixture, request):
        source = request.getfixturevalue(source_fixture)
        assert source.get_latest("UNKNOWN") is None

    def test_get_all_latest_empty(self, source_fixture, request):
        source = request.getfixturevalue(source_fixture)
        assert source.get_all_latest() == {}
```

---

## 16. Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `MASSIVE_API_KEY` | *(empty)* | If set, use Massive API; if empty, use simulator |
| `MASSIVE_POLL_INTERVAL` | `15.0` | Seconds between Massive API polls |
| `SIMULATOR_TICK_INTERVAL` | `0.5` | Seconds between simulator ticks |

| Constant | Value | Location |
|---|---|---|
| `INTRA_SECTOR_CORRELATION` | `0.6` | `engine.py` |
| `EVENT_PROBABILITY` | `0.02` | `engine.py` |
| `EVENT_MIN_MAGNITUDE` | `0.02` | `engine.py` |
| `EVENT_MAX_MAGNITUDE` | `0.05` | `engine.py` |
| `MIN_PRICE` | `0.01` | `engine.py` |
| `DEFAULT_SEED_RANGE` | `(50.0, 300.0)` | `seed_prices.py` |
| SSE push interval | `0.5s` | `sse.py` |
| SSE retry directive | `1000ms` | `sse.py` |

---

## Module `__init__.py`

**File: `backend/src/market/__init__.py`**

```python
"""Market data subsystem — unified interface for price streaming.

Usage:
    from market import create_market_data_source, MarketDataSource, PriceUpdate

    source = create_market_data_source()  # Reads MASSIVE_API_KEY env var
    source.register_ticker("AAPL")
    await source.start()

    update = source.get_latest("AAPL")
    print(update.price, update.direction)

    await source.stop()
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate

__all__ = [
    "create_market_data_source",
    "MarketDataSource",
    "PriceCache",
    "PriceUpdate",
]
```
