# Market Data Backend -- Summary

**Status:** Complete, tested, reviewed, all issues resolved.

## What Was Built

A complete market data subsystem in `backend/src/market/` (9 modules, ~600 lines) providing live price simulation and real market data via a unified interface.

### Architecture

```
MarketDataSource (ABC)
├── SimulatorMarketData  ->  GBM simulator (default, no API key needed)
└── MassiveMarketData    ->  Massive/Polygon.io REST poller (when MASSIVE_API_KEY set)
        |
        v
   PriceCache (thread-safe, in-memory)
        |
        |-->  SSE stream endpoint (GET /api/stream/prices)
        |-->  Portfolio valuation (future)
        '-->  Trade execution (future)
```

### Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` -- immutable frozen dataclass with `Literal` direction type |
| `interface.py` | `MarketDataSource` -- abstract base class defining `start/stop/register_ticker/unregister_ticker/get_latest/get_all_latest` |
| `cache.py` | `PriceCache` -- thread-safe price store with direction computation on write |
| `seed_prices.py` | Realistic seed prices, per-ticker GBM params (drift/volatility/sector) |
| `engine.py` | `SimulationEngine` -- GBM math with correlated sector moves and random events |
| `simulator.py` | `SimulatorMarketData` -- MarketDataSource implementation using the GBM engine |
| `massive_client.py` | `MassiveMarketData` -- REST polling client for Massive (Polygon.io) using httpx |
| `factory.py` | `create_market_data_source()` -- selects simulator or Massive based on `MASSIVE_API_KEY` env var |
| `sse.py` | FastAPI SSE streaming endpoint at `/api/stream/prices` |

### Key Design Decisions

- **Strategy pattern** -- both data sources implement the same ABC; downstream code is source-agnostic
- **PriceCache as single point of truth** -- producers write, consumers read; no direct coupling
- **GBM with correlated moves** -- sector-based correlation (rho=0.6); tech stocks move together, financials move together
- **Random shock events** -- 2% chance per tick of a 2-5% sudden move on one random ticker for visual drama
- **SSE over WebSockets** -- simpler, one-way push, universal browser support
- **Lazy imports in factory** -- httpx only imported when Massive client is actually used

## Test Suite

**55 tests, all passing.** 7 test modules in `backend/tests/`.

| Module | Tests | What It Covers |
|--------|-------|----------------|
| `test_models.py` | 3 | Frozen enforcement, to_dict serialization |
| `test_cache.py` | 10 | Direction logic, rounding, remove, get_all copy safety |
| `test_engine.py` | 15 | Seed prices, determinism, positivity, sector correlation, event mechanism |
| `test_simulator.py` | 6 | Async start/stop, register/unregister, interface conformance |
| `test_massive_client.py` | 11 | Response parsing, 401/403/429 handling, network errors, missing fields |
| `test_factory.py` | 6 | Env var logic, empty/whitespace keys, interval configuration |
| `test_sse.py` | 4 | Response headers, retry directive, event format, empty cache |

## Code Review & Fixes Applied

A comprehensive code review (see `planning/MARKET_DATA_REVIEW.md`) identified 4 important issues and 3 suggestions. All were resolved:

1. **SSE endpoint tests added** -- 4 tests covering headers, retry directive, event format, empty cache
2. **Sector correlation test added** -- validates intra-sector correlation > cross-sector correlation
3. **Ticker set snapshot in Massive client** -- `_fetch_and_update` now snapshots the ticker set before iterating to avoid concurrent modification
4. **Base URL updated** -- changed from legacy `api.polygon.io` to canonical `api.massive.com`
5. **Literal type for direction** -- `PriceUpdate.direction` now uses `Literal["up", "down", "unchanged"]`
6. **Ticker uppercasing normalized** -- uppercasing at the interface boundary in simulator
7. **Additional test coverage** -- event mechanism, cache copy safety, HTTP 401/403 error handling

## Usage for Downstream Code

```python
from src.market import PriceCache, create_market_data_source

# Startup
source = create_market_data_source()  # Reads MASSIVE_API_KEY env var

# Register tickers
for ticker in ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]:
    source.register_ticker(ticker)

await source.start()

# Read prices
update = source.get_latest("AAPL")      # PriceUpdate or None
all_prices = source.get_all_latest()     # dict[str, PriceUpdate]

# Dynamic watchlist
source.register_ticker("PYPL")
source.unregister_ticker("GOOGL")

# Shutdown
await source.stop()
```
