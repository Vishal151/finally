"""Pydantic models for structured LLM responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    ticker: str
    side: str  # "buy" or "sell"
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    ticker: str
    action: str  # "add" or "remove"


class LLMResponse(BaseModel):
    """Structured output schema for the LLM."""
    message: str
    trades: list[TradeRequest] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
