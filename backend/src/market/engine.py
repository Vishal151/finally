"""GBM-based price simulation engine with correlated moves and random events."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

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

    price: float
    mu: float
    sigma: float
    sector: str


INTRA_SECTOR_CORRELATION = 0.6

EVENT_PROBABILITY = 0.02
EVENT_MIN_MAGNITUDE = 0.02
EVENT_MAX_MAGNITUDE = 0.05

MIN_PRICE = 0.01


class SimulationEngine:
    """Generates correlated GBM price updates for all registered tickers.

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
        # Convert tick interval (seconds) to fraction of a trading year
        self._dt = tick_interval / (252 * 6.5 * 3600)
        self._rng = random.Random(seed)

    def add_ticker(self, ticker: str, seed_price: float | None = None) -> None:
        """Register a ticker for simulation."""
        ticker = ticker.upper()
        if ticker in self._tickers:
            return

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
        """Advance all tickers by one time step. Returns {ticker: new_price}."""
        if not self._tickers:
            return {}

        # Group tickers by sector
        sectors: dict[str, list[str]] = defaultdict(list)
        for ticker, params in self._tickers.items():
            sectors[params.sector].append(ticker)

        # Generate one shared random shock per sector
        sector_shocks: dict[str, float] = {
            sector: self._rng.gauss(0, 1) for sector in sectors
        }

        # Determine if a random event fires this tick
        event_ticker: str | None = None
        event_shock: float = 0.0
        if self._rng.random() < EVENT_PROBABILITY and self._tickers:
            event_ticker = self._rng.choice(list(self._tickers.keys()))
            magnitude = self._rng.uniform(EVENT_MIN_MAGNITUDE, EVENT_MAX_MAGNITUDE)
            event_shock = magnitude if self._rng.random() > 0.5 else -magnitude

        # Apply GBM to each ticker
        rho = INTRA_SECTOR_CORRELATION
        rho_complement = math.sqrt(1 - rho ** 2)
        results: dict[str, float] = {}

        for ticker, params in self._tickers.items():
            z_sector = sector_shocks[params.sector]
            z_individual = self._rng.gauss(0, 1)
            z = rho * z_sector + rho_complement * z_individual

            drift = (params.mu - 0.5 * params.sigma ** 2) * self._dt
            diffusion = params.sigma * math.sqrt(self._dt) * z
            new_price = params.price * math.exp(drift + diffusion)

            if ticker == event_ticker:
                new_price *= (1 + event_shock)

            new_price = max(new_price, MIN_PRICE)

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
