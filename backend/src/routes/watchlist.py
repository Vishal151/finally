"""Watchlist API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..database import queries
from ..market.seed_prices import SEED_PRICES

router = APIRouter()


class AddTickerRequest(BaseModel):
    ticker: str


@router.get("/api/watchlist")
async def get_watchlist(request: Request):
    """Current watchlist tickers with latest prices."""
    market_data = request.app.state.market_data
    tickers = queries.get_watchlist_tickers()
    items = []
    for ticker in tickers:
        price_update = market_data.get_latest(ticker)
        item = {"ticker": ticker}
        if price_update:
            item.update(price_update.to_dict())
        items.append(item)
    return {"watchlist": items}


@router.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest, request: Request):
    """Add a ticker to the watchlist."""
    market_data = request.app.state.market_data
    ticker = body.ticker.upper()

    try:
        entry = queries.add_to_watchlist(ticker)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    seed_price = SEED_PRICES.get(ticker)
    market_data.register_ticker(ticker, seed_price)

    return entry


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, request: Request):
    """Remove a ticker from the watchlist."""
    market_data = request.app.state.market_data
    ticker = ticker.upper()

    removed = queries.remove_from_watchlist(ticker)
    if not removed:
        return JSONResponse(status_code=404, content={"error": f"{ticker} not in watchlist"})

    market_data.unregister_ticker(ticker)
    return {"removed": ticker}
