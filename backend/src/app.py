"""FastAPI application for FinAlly trading workstation."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import get_db, init_db
from .database import queries
from .market import create_market_data_source
from .market.sse import router as sse_router
from .routes.chat import router as chat_router
from .routes.health import router as health_router
from .routes.portfolio import router as portfolio_router
from .routes.portfolio import _snapshot_portfolio
from .routes.watchlist import router as watchlist_router

logger = logging.getLogger(__name__)

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            import os
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


async def _snapshot_loop(app: FastAPI) -> None:
    """Record portfolio snapshots every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            _snapshot_portfolio(app.state.market_data)
        except Exception:
            logger.exception("Error recording portfolio snapshot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Start market data source
    market_data = create_market_data_source()
    app.state.market_data = market_data

    # Register watchlist tickers with market data source
    tickers = queries.get_watchlist_tickers()
    for ticker in tickers:
        market_data.register_ticker(ticker)
    logger.info("Registered %d watchlist tickers", len(tickers))

    await market_data.start()
    logger.info("Market data source started")

    # Start portfolio snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_loop(app))

    yield

    # Shutdown
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass
    await market_data.stop()
    logger.info("Shutdown complete")


app = FastAPI(title="FinAlly", lifespan=lifespan)

# Mount API routers
app.include_router(health_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)
app.include_router(sse_router)

# Serve static frontend files (if the directory exists)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
