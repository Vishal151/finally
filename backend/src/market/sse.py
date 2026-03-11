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

    Event format:
        data: {"ticker":"AAPL","price":191.25,...,"direction":"up"}
    """
    source: MarketDataSource = request.app.state.market_data

    async def event_generator():
        yield "retry: 1000\n\n"

        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                break

            updates = source.get_all_latest()
            for update in updates.values():
                data = json.dumps(update.to_dict())
                yield f"data: {data}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
