"""Core data model for price updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Direction = Literal["up", "down", "unchanged"]


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
    direction: Direction

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON encoding in the SSE stream."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.prev_price,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
        }
