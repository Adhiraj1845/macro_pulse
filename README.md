# Macro Pulse

A full-stack macroeconomic analytics platform with a REST API, interactive web dashboard, and Claude Desktop integration via MCP (Model Context Protocol).

Tracks macroeconomic indicators and financial market assets, with analytical endpoints for correlation analysis, recession risk scoring, sector impact analysis, and macro trend detection.

Built with **FastAPI**, **SQLAlchemy**, and **SQLite** (PostgreSQL-ready), consuming live data from the **FRED API** and **Yahoo Finance**.

---

## API Documentation

Full API documentation is provided as a PDF generated from the live Swagger UI:

**[`Macro & Market Impact Analytics API - Swagger UI.pdf`](Macro%20%26%20Market%20Impact%20Analytics%20API%20-%20Swagger%20UI.pdf)**

The PDF covers all 20 endpoints across five resource groups (Health, Indicators, Assets, Snapshots & Ingestion, Analytics), including request parameters, response schemas, and error codes for every endpoint.

Interactive documentation is also available when the server is running:

| UI | URL | Description |
|----|-----|-------------|
| Swagger UI | `/docs` | Try endpoints live in the browser |
| ReDoc | `/redoc` | Clean, readable reference layout |
| OpenAPI JSON | `/openapi.json` | Raw OpenAPI 3.1 schema |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/adhiraj1845/macro_pulse.git
cd macro_pulse
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your FRED API key (free at https://fred.stlouisfed.org/docs/api/api_key.html):

```
FRED_API_KEY=your_fred_api_key_here
DATABASE_URL=sqlite:///./macro_api.db
```

### 5. Seed the database

```bash
python scripts/seed_data.py
```

This creates 62 default assets (ETFs, equities, commodities, bonds, international) and 7 macro indicators, then downloads their full historical data from FRED and Yahoo Finance in a single batch request.

### 6. Run the API

```bash
uvicorn main:app --reload
```

The dashboard is at **http://127.0.0.1:8000** and the API at **http://127.0.0.1:8000/api/v1**.

---

## Project Structure

```
macro_pulse/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── Procfile                    # Heroku deployment config
├── runtime.txt                 # Python runtime version
│
├── app/
│   ├── config.py               # Pydantic settings (env vars)
│   ├── database.py             # SQLAlchemy engine, session, Base
│   ├── mcp_server.py           # Model Context Protocol server
│   │
│   ├── models/
│   │   └── models.py           # MacroIndicator, IndicatorSnapshot, MarketAsset, AssetSnapshot
│   │
│   ├── schemas/
│   │   ├── indicator.py        # Pydantic schemas for indicators & snapshots
│   │   ├── asset.py            # Pydantic schemas for assets & price snapshots
│   │   └── analytics.py        # Pydantic schemas for all analytics responses
│   │
│   ├── routers/
│   │   ├── indicators.py       # CRUD endpoints for macro indicators
│   │   ├── assets.py           # CRUD endpoints for market assets
│   │   ├── snapshots.py        # Ingestion + snapshot query endpoints
│   │   └── analytics.py        # 5 analytical endpoints
│   │
│   └── services/
│       ├── ingestion.py        # FRED and Yahoo Finance data ingestion
│       └── analytics.py        # Correlation, recession risk, trend, sector impact
│
├── scripts/
│   ├── seed_data.py            # Database seeding and bulk ingestion script
│   └── run_mcp.py              # MCP server entry point for Claude Desktop
│
├── tests/
│   └── test_api.py             # Pytest integration tests (36 tests)
│
├── static/
│   └── index.html              # Interactive web dashboard
│
└── api_docs.pdf                # Full API documentation (PDF)
```

---

## API Endpoints Overview

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health check and version info |

### Indicators

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/indicators` | List all indicators (filter by `category`) |
| POST | `/api/v1/indicators` | Create a new indicator |
| GET | `/api/v1/indicators/{id}` | Get indicator with full snapshot history |
| PATCH | `/api/v1/indicators/{id}` | Partially update an indicator |
| DELETE | `/api/v1/indicators/{id}` | Delete indicator and all snapshots |

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/assets` | List all assets (filter by `sector`, `asset_class`, `country`) |
| POST | `/api/v1/assets` | Create a new asset |
| GET | `/api/v1/assets/{id}` | Get asset with full price history |
| PATCH | `/api/v1/assets/{id}` | Partially update an asset |
| DELETE | `/api/v1/assets/{id}` | Delete asset and all price snapshots |

### Snapshots & Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/snapshots/indicators/{id}/ingest` | Pull full history from FRED |
| GET | `/api/v1/snapshots/indicators/{id}` | Query indicator time-series (date range) |
| POST | `/api/v1/snapshots/assets/{id}/ingest` | Pull full history from Yahoo Finance |
| GET | `/api/v1/snapshots/assets/{id}` | Query asset OHLCV price history (date range) |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/correlation` | Pearson correlation between indicator and asset |
| GET | `/api/v1/analytics/recession-risk` | Composite recession risk score (0–100) |
| GET | `/api/v1/analytics/macro-trend/{id}` | Trend direction and magnitude over N periods |
| GET | `/api/v1/analytics/sector-impact/{id}` | Correlation with all tracked assets |
| GET | `/api/v1/analytics/market-summary` | Latest values and trends for all data |

---

## Running Tests

```bash
pytest tests/ -v
```

36 integration tests covering all CRUD operations and analytics endpoints. Tests use an in-memory SQLite database and never touch production data.

---

## Design Decisions

### REST over GraphQL
Analytical endpoints return computed results (correlations, regression slopes) rather than flexible object graphs. The server must run the full computation regardless of which fields are requested, so GraphQL's flexibility offers no benefit. REST fits naturally with HTTP caching and is simpler to document and test.

### Normalised Schema (2NF)
Indicator metadata and time-series observations are in separate tables (`indicators` / `indicator_snapshots`). This eliminates redundant repetition of metadata on every observation row and enables composite indexes on `(indicator_id, date)` for fast date-range queries.

### SQLAlchemy ORM — SQLite → PostgreSQL Pathway
All database interaction goes through SQLAlchemy. Switching to PostgreSQL requires only changing `DATABASE_URL` in `.env`. No model, query, or router code changes.

### Service Layer Separation
Business logic (ingestion, analytics) lives in `app/services/`, completely separate from HTTP concerns in `app/routers/`. Analytics functions are independently testable and the data source can be swapped without touching any router code.

### Idempotent Ingestion
The ingestion service checks existing dates before inserting, making every ingest call safe to repeat. For the seed script, `yf.download()` is used to batch all new tickers into a single HTTP request, avoiding Yahoo Finance rate limits.

---

## Claude Desktop Integration (MCP)

Macro Pulse exposes its analytics as MCP tools, enabling natural-language queries backed by live data from your local database.

### Setup

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "macro-pulse": {
      "command": "/path/to/python",
      "args": ["/path/to/macro_pulse/scripts/run_mcp.py"]
    }
  }
}
```

On Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Fully quit and relaunch Claude Desktop after editing.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `get_market_summary` | Latest values and trends for all indicators and assets |
| `get_recession_risk` | Composite recession risk score (0–100) with signal breakdown |
| `get_correlation` | Pearson correlation between any indicator and asset |
| `get_macro_trend` | Trend direction and magnitude for any indicator |
| `get_sector_impact` | Which assets are most exposed to a given macro variable |
| `list_indicators` | All tracked indicators with IDs |
| `list_assets` | All tracked assets with IDs |

### Example Prompts

- *"What is the current recession risk score and which signals are elevated?"*
- *"How correlated is the yield curve with SPY over the past 2 years?"*
- *"Which sectors are most exposed to changes in CPI?"*
- *"Is unemployment trending up or down over the last 24 months?"*

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `sqlalchemy` | ORM and database abstraction |
| `pydantic` | Data validation and serialisation |
| `pydantic-settings` | Environment variable management |
| `fredapi` | FRED API client |
| `yfinance` | Yahoo Finance price data |
| `pandas` | Time-series alignment and resampling |
| `numpy` | Linear regression for trend detection |
| `scipy` | Pearson correlation coefficient |
| `mcp` | Model Context Protocol server |
| `pytest` | Integration testing |

---

## Data Sources

- **FRED (Federal Reserve Economic Data)** — macroeconomic indicators. Free API key at https://fred.stlouisfed.org
- **Yahoo Finance** — market asset OHLCV price history via `yfinance`. No authentication required.