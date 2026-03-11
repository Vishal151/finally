"""Seed prices and GBM parameters for the market simulator."""

from __future__ import annotations

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

DEFAULT_SEED_RANGE: tuple[float, float] = (50.0, 300.0)

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

DEFAULT_MU = 0.08
DEFAULT_SIGMA = 0.25
DEFAULT_SECTOR = "other"
