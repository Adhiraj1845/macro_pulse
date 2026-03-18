# 📊 Macro Pulse

A production-quality REST API for tracking macroeconomic indicators and financial market assets, with analytical endpoints for correlation analysis, recession risk scoring, sector impact analysis, and macro trend detection.

Built with **FastAPI**, **SQLAlchemy**, and **SQLite** (PostgreSQL-ready), consuming data from the **FRED API** and **Yahoo Finance**.

---

## 🚀 Quick Start

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

# macOS/Linux
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

This populates 7 default indicators and 14 market assets, and optionally ingests all historical data from FRED and Yahoo Finance.

### 6. Run the API

```bash
uvicorn main:app --reload
```

Visit **http://127.0.0.1:8000/docs** for the interactive Swagger UI.

---

## 📁 Project Structure

```
macro_pulse/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── .gitignore
│
├── app/
│   ├── config.py               # Settings via pydantic-settings
│   ├── database.py             # SQLAlchemy engine, session, Base
│   │
│   ├── models/
│   │   └── models.py           # MacroIndicator, IndicatorSnapshot, MarketAsset, AssetSnapshot
│   │
│   ├── schemas/
│   │   ├── indicator.py        # Pydantic schemas for indicators
│   │   ├── asset.py            # Pydantic schemas for assets
│   │   └── analytics.py        # Pydantic schemas for analytics responses
│   │
│   ├── routers/
│   │   ├── indicators.py       # CRUD endpoints for indicators
│   │   ├── assets.py           # CRUD endpoints for assets
│   │   ├── snapshots.py        # Ingestion + snapshot query endpoints
│   │   └── analytics.py        # Analytics endpoints
│   │
│   └── services/
│       ├── ingestion.py        # FRED and Yahoo Finance data ingestion
│       └── analytics.py        # Correlation, recession risk, trend, sector impact
│
├── scripts/
│   └── seed_data.py            # Database seeding script
│
├── tests/
│   └── test_api.py             # Pytest integration tests
│
└── static/                     # Frontend dashboard (Stage 7)
```

---

## 🔌 API Endpoints

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health check |

### Indicators

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/indicators` | List all indicators (filter by `category`) |
| POST | `/api/v1/indicators` | Create a new indicator |
| GET | `/api/v1/indicators/{id}` | Get indicator with snapshot history |
| PATCH | `/api/v1/indicators/{id}` | Partially update an indicator |
| DELETE | `/api/v1/indicators/{id}` | Delete indicator and all snapshots |

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/assets` | List all assets (filter by `sector`, `asset_class`, `country`) |
| POST | `/api/v1/assets` | Create a new asset |
| GET | `/api/v1/assets/{id}` | Get asset with price history |
| PATCH | `/api/v1/assets/{id}` | Partially update an asset |
| DELETE | `/api/v1/assets/{id}` | Delete asset and all snapshots |

### Snapshots & Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/snapshots/indicators/{id}/ingest` | Pull full history from FRED |
| GET | `/api/v1/snapshots/indicators/{id}` | Query indicator time-series (date range filter) |
| POST | `/api/v1/snapshots/assets/{id}/ingest` | Pull full history from Yahoo Finance |
| GET | `/api/v1/snapshots/assets/{id}` | Query asset price history (date range filter) |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/correlation` | Pearson correlation between indicator and asset |
| GET | `/api/v1/analytics/recession-risk` | Composite recession risk score (0–100) |
| GET | `/api/v1/analytics/macro-trend/{id}` | Trend direction and magnitude over N periods |
| GET | `/api/v1/analytics/sector-impact/{id}` | Correlation with all assets grouped by sector |
| GET | `/api/v1/analytics/market-summary` | Latest values for all indicators and assets |

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database and never touch your real data.

---

## 📡 Example Requests

### Create an indicator

```bash
curl -X POST http://127.0.0.1:8000/api/v1/indicators \
  -H "Content-Type: application/json" \
  -d '{
    "fred_series_id": "CPIAUCSL",
    "name": "Consumer Price Index",
    "category": "inflation",
    "unit": "Index 1982-84=100",
    "frequency": "Monthly",
    "source": "FRED"
  }'
```

### Ingest data from FRED

```bash
curl -X POST http://127.0.0.1:8000/api/v1/snapshots/indicators/1/ingest
```

### Get recession risk score

```bash
curl http://127.0.0.1:8000/api/v1/analytics/recession-risk
```

### Correlation between CPI and SPY

```bash
curl "http://127.0.0.1:8000/api/v1/analytics/correlation?indicator_id=1&asset_id=1"
```

### Sector impact of CPI

```bash
curl http://127.0.0.1:8000/api/v1/analytics/sector-impact/1
```

---

## 🏗️ Design Decisions

### REST over GraphQL
The API's analytical endpoints return computed results rather than flexible object graphs. GraphQL's flexibility is largely wasted when the server must run a full correlation or regression model regardless of which fields the client requests. REST fits naturally with HTTP caching and is simpler to document and test.

### Normalised schema (2NF)
Indicator metadata and time-series observations are stored in separate tables (`indicators` and `indicator_snapshots`). This avoids repeating metadata (name, unit, source) on every observation row, and allows composite indexes on `(indicator_id, date)` for fast range queries.

### SQLAlchemy ORM with SQLite → PostgreSQL pathway
All database interaction goes through SQLAlchemy's ORM, meaning the only change required to switch to PostgreSQL is the `DATABASE_URL` environment variable. No model, query, or router code needs to change.

### Service layer separation
Business logic (ingestion, analytics) lives in `app/services/`, completely separate from HTTP concerns in `app/routers/`. This makes the analytics functions independently testable and means the data source could be swapped without touching any router code.

### Idempotent ingestion
The ingestion service checks existing dates before inserting, making it safe to call repeatedly. This is important for keeping data current without risk of duplication.

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `sqlalchemy` | ORM and database abstraction |
| `pydantic` | Data validation and serialisation |
| `pydantic-settings` | Environment variable management |
| `fredapi` | FRED API client |
| `yfinance` | Yahoo Finance data |
| `pandas` | Time-series alignment and resampling |
| `numpy` | Linear regression for trend detection |
| `scipy` | Pearson correlation |
| `pytest` | Integration testing |

---

## 🔑 Data Sources

- **FRED (Federal Reserve Economic Data)** — macroeconomic indicators. Free API key required at https://fred.stlouisfed.org
- **Yahoo Finance** — market asset price history via `yfinance`. No authentication required.

---

## 📄 API Documentation

Full API documentation is available at `/docs` (Swagger UI) when the server is running.
A PDF export of the API documentation is included in the repository as `api_docs.pdf`.