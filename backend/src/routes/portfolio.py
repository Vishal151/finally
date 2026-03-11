"""Portfolio API routes — positions, trading, and history."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..database import queries

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    side: str = Field(pattern="^(buy|sell)$")


@router.get("/api/portfolio")
async def get_portfolio(request: Request):
    """Current positions, cash balance, total value, and unrealized P&L."""
    market_data = request.app.state.market_data
    profile = queries.get_portfolio()
    positions = queries.get_positions()

    total_positions_value = 0.0
    enriched_positions = []
    for pos in positions:
        ticker = pos["ticker"]
        price_update = market_data.get_latest(ticker)
        current_price = price_update.price if price_update else pos["avg_cost"]
        market_value = round(current_price * pos["quantity"], 2)
        unrealized_pnl = round((current_price - pos["avg_cost"]) * pos["quantity"], 2)
        pct_change = round((current_price / pos["avg_cost"] - 1) * 100, 2) if pos["avg_cost"] else 0.0
        total_positions_value += market_value

        enriched_positions.append({
            "ticker": ticker,
            "quantity": pos["quantity"],
            "avg_cost": pos["avg_cost"],
            "current_price": current_price,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "pnl_percent": pct_change,
        })

    total_value = round(profile["cash_balance"] + total_positions_value, 2)

    return {
        "cash_balance": profile["cash_balance"],
        "positions": enriched_positions,
        "total_value": total_value,
    }


@router.post("/api/portfolio/trade")
async def execute_trade(trade: TradeRequest, request: Request):
    """Execute a market order trade."""
    market_data = request.app.state.market_data
    ticker = trade.ticker.upper()

    price_update = market_data.get_latest(ticker)
    if not price_update:
        return JSONResponse(status_code=400, content={"error": f"No price available for {ticker}"})

    try:
        trade_record = queries.execute_trade(
            ticker=ticker,
            side=trade.side,
            quantity=trade.quantity,
            price=price_update.price,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    profile = queries.get_portfolio()
    position = queries.get_position(ticker)

    # Snapshot portfolio value after trade
    _snapshot_portfolio(market_data)

    return {
        "trade": trade_record,
        "cash_balance": profile["cash_balance"],
        "position": {
            "ticker": position["ticker"],
            "quantity": position["quantity"],
            "avg_cost": position["avg_cost"],
        } if position else None,
    }


@router.get("/api/portfolio/history")
async def get_portfolio_history():
    """Portfolio value snapshots for P&L chart."""
    snapshots = queries.get_snapshots()
    return {"snapshots": snapshots}


def _snapshot_portfolio(market_data) -> None:
    """Compute current portfolio value and record a snapshot."""
    profile = queries.get_portfolio()
    positions = queries.get_positions()
    total = profile["cash_balance"]
    for pos in positions:
        price_update = market_data.get_latest(pos["ticker"])
        price = price_update.price if price_update else pos["avg_cost"]
        total += price * pos["quantity"]
    queries.record_snapshot(round(total, 2))
