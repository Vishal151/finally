# Market Data Backend -- Code Review

## Review Scope

- **Source files**: 10 files in `backend/src/market/`
- **Test files**: 7 files in `backend/tests/`
- **Design specs**: `planning/MARKET_DATA_DESIGN.md`, `planning/MARKET_INTERFACE.md`, `planning/MARKET_SIMULATOR.md`, `planning/MASSIVE_API.md`, `planning/PLAN.md`

---

## 1. Test Results

**46 tests, 46 passed, 0 failed** (Python 3.13.7, pytest 9.0.2, 0.61s)

| Module | Test File | Tests | Assessment |
|--------|-----------|-------|------------|
| `models.py` | `test_models.py` | 3 | Good: frozen enforcement, to_dict serialization |
| `cache.py` | `test_cache.py` | 9 | Good: direction logic, rounding, remove, get_all |
| `engine.py` | `test_engine.py` | 12 | Good: seed prices, determinism, positivity over 1000 ticks |
| `simulator.py` | `test_simulator.py` | 6 | Adequate: async start/stop, register/unregister, interface check |
| `massive_client.py` | `test_massive_client.py` | 9 | Good: response parsing, error handling (429, network, missing fields) |
| `factory.py` | `test_factory.py` | 6 | Good: env var logic, empty/whitespace keys, interval config |

### Coverage Gaps

**Missing tests:**

1. **SSE endpoint (`sse.py`) has zero tests.** This is the most user-facing component. Should test: correct content type/headers, valid SSE event format, retry directive, empty cache behavior.

2. **Sector correlation test not implemented.** The design spec (MARKET_DATA_DESIGN.md Section 15) specifies a `test_sector_correlation` validating `corr(AAPL, MSFT) > corr(AAPL, JPM)`. This is a key validation of the GBM correlation model.

3. **No `get_all` copy-safety test for PriceCache.** The implementation correctly returns `dict(self._prices)`, but no test validates mutating the returned dict does not affect the cache.

4. **No parametrized interface conformance tests.** The design spec calls for a shared test class that runs against both implementations. Only `issubclass` checks exist.

5. **No test for HTTP 401 or 403 responses on Massive client.** These paths are handled in code but not tested.

6. **No test verifying the event mechanism fires.** The 2% probability path is likely exercised in the 1000-tick test but never asserted.

---

## 2. Architecture Assessment

### Plan Alignment

The implementation matches the design spec with high fidelity. Every file specified in MARKET_DATA_DESIGN.md Section 2 exists with the expected name and purpose. Class signatures, method names, and data flow match the spec.

**Minor deviations (all cosmetic):**

| Deviation | Verdict |
|-----------|---------|
| `simulator.py` omits debug logging on register/unregister | No functional impact |
| `simulator.py` omits "tick loop started" log message | No functional impact |
| `sse.py` iterates `updates.values()` not `updates.items()` | Functionally equivalent |
| `__init__.py` omits usage docstring from spec | Cosmetic |

### ABC Pattern

Clean and minimal. All six abstract methods implemented by both `SimulatorMarketData` and `MassiveMarketData`. Return types are correct. Both implementations properly extend the ABC.

### Separation of Concerns

Excellent decomposition:
- `engine.py` -- pure GBM math, synchronous, no I/O
- `cache.py` -- thread-safe price storage, no market logic
- `simulator.py` -- orchestrates engine + cache + async task
- `massive_client.py` -- orchestrates HTTP polling + cache + async task
- `sse.py` -- thin read-only consumer of the cache via the interface
- `factory.py` -- simple env-var dispatcher with lazy imports

### Thread Safety

`PriceCache` uses `threading.Lock` for all mutations and reads. Correct for the current architecture. `SimulationEngine` is not thread-safe but is only called from a single async task, which is acceptable.

### Error Handling

- **Simulator tick loop**: catches all exceptions and continues. Correct -- a bad tick should not kill the stream.
- **Massive client**: differentiates 429/401/403 with appropriate log levels. Tracks `_consecutive_errors` but doesn't act on it (no circuit breaker). Fine for current scope.
- **SSE endpoint**: checks `request.is_disconnected()` to break cleanly. No exception handling around `get_all_latest()` or `json.dumps()`, but these are low-risk operations.

---

## 3. Actionable Issues

### Important (Should Fix)

**I-1. No tests for `sse.py`**
- Location: `backend/tests/` (missing `test_sse.py`)
- The SSE endpoint is the primary delivery mechanism for price data to the frontend. Test with FastAPI's `TestClient` to catch regressions in event format, headers, and disconnection behavior.

**I-2. Missing sector correlation test**
- Location: `backend/tests/test_engine.py`
- The design spec explicitly calls for this test. Without it, a regression in the correlation model would go undetected. Port the test from MARKET_DATA_DESIGN.md Section 15.

**I-3. `MassiveMarketData._tickers` has no synchronization**
- Location: `backend/src/market/massive_client.py:38`
- `register_ticker` adds to `self._tickers` from request handlers while `_poll_loop` reads/iterates it. Safe in single-threaded asyncio due to CPython's GIL, but fragile. The `sorted()` call on line 90 could theoretically see a partial state.
- Fix: use `sorted(set(self._tickers))` in `_fetch_and_update` to snapshot the set, or document the single-thread assumption.

**I-4. Base URL uses legacy `api.polygon.io` instead of `api.massive.com`**
- Location: `backend/src/market/massive_client.py:17`
- `MASSIVE_API.md` states the legacy domain still works but the canonical URL is `https://api.massive.com`. Could break if the legacy domain is retired.
- Fix: update `BASE_URL` to `https://api.massive.com` or make configurable via env var.

### Suggestions (Nice to Have)

**S-1. `PriceUpdate.direction` is an unconstrained `str`**
- Location: `backend/src/market/models.py:21`
- Could be `Literal["up", "down", "unchanged"]` for type safety.

**S-2. SSE pushes ALL tickers every 500ms regardless of changes**
- Location: `backend/src/market/sse.py:36-39`
- Fine for 10 tickers. Matches spec. Note as future optimization point for larger watchlists.

**S-3. Ticker uppercasing is scattered across multiple layers**
- `get_latest`, `unregister_ticker`, `register_ticker`, and `engine.add_ticker` all uppercase independently. Not a bug, but normalizing at a single entry point would improve maintainability.

---

## 4. What Was Done Well

1. **Faithful spec implementation.** Code matches design documents almost exactly -- data structures, method signatures, error handling, module boundaries.

2. **Clean module decomposition.** The `engine.py` / `simulator.py` split keeps pure math separate from async orchestration, making the engine trivially testable.

3. **Frozen dataclass with slots.** `PriceUpdate` is immutable and memory-efficient.

4. **Deterministic testing via seed parameter.** `SimulationEngine` accepts an optional seed, enabling reproducible tests.

5. **httpx MockTransport for Massive client tests.** Idiomatic and produces clean, realistic HTTP tests.

6. **Lazy imports in factory.** Avoids importing `httpx` when running the simulator.

7. **Price rounding in the cache.** Consistent 2-decimal precision throughout the system.

8. **Robust Massive error handling.** Differentiated 429/401/403 handling with appropriate log levels.

---

## 5. Summary

| Category | Count |
|----------|-------|
| Critical issues | 0 |
| Important issues | 4 |
| Suggestions | 3 |

The market data backend is well-implemented and closely follows its design spec. The architecture is clean, the code is readable, and the existing 46 tests are solid. The main gaps are: (1) no SSE endpoint tests, (2) a missing correlation test from the spec, (3) a minor thread-safety fragility in the Massive client, and (4) the base URL should use the canonical Massive domain. None are blocking, but I-1 and I-2 should be addressed before the next build phase to maintain test coverage standards.
