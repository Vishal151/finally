# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Quick Start

```bash
# Configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Run with Docker (macOS/Linux)
./scripts/start_mac.sh

# Or with Docker manually
docker compose up --build

# Or run locally (backend only)
cd backend && uv sync && uv run uvicorn src.app:app --port 8000

# Open http://localhost:8000
```

To stop: `./scripts/stop_mac.sh` or `docker compose down`

Windows users: use `scripts/start_windows.ps1` and `scripts/stop_windows.ps1`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |
| `DATABASE_PATH` | No | SQLite path; defaults to `../db/finally.db` relative to backend |

## Testing

```bash
# Backend unit tests (118 tests)
cd backend && uv run pytest

# E2E Playwright tests (20 tests)
cd test && npm install && npx playwright test
```

## Project Structure

```
finally/
├── frontend/    # Next.js static export (TypeScript, Tailwind CSS)
├── backend/     # FastAPI uv project (Python)
│   ├── src/
│   │   ├── market/     # Market data simulator + Massive API client
│   │   ├── database/   # SQLite layer (schema, queries)
│   │   ├── llm/        # LLM chat integration (OpenRouter/Cerebras)
│   │   ├── routes/     # API endpoints
│   │   └── app.py      # FastAPI application
│   └── db/             # SQL schema and seed files
├── test/        # Playwright E2E tests
├── scripts/     # Docker start/stop scripts (macOS, Windows)
├── db/          # SQLite volume mount (runtime, gitignored)
└── planning/    # Project documentation
```
