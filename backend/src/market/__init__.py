"""Market data subsystem — unified interface for price streaming.

Public API:
    MarketDataSource    — abstract interface (ABC)
    PriceUpdate         — immutable price update value object
    PriceCache          — thread-safe in-memory price store
    create_market_data_source() — factory function
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate

__all__ = [
    "MarketDataSource",
    "PriceUpdate",
    "PriceCache",
    "create_market_data_source",
]
