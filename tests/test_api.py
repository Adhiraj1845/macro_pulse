"""
Integration Tests
-----------------
Tests all CRUD operations, error codes, and analytics endpoints.
Uses an in-memory SQLite database — never touches your real macro_api.db.

Run with:
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from main import app

# ---------------------------------------------------------------------------
# Test database setup — in-memory SQLite, isolated per test session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INDICATOR_PAYLOAD = {
    "fred_series_id": "CPIAUCSL",
    "name": "Consumer Price Index",
    "description": "CPI for all urban consumers",
    "category": "inflation",
    "unit": "Index 1982-84=100",
    "frequency": "Monthly",
    "source": "FRED",
}

ASSET_PAYLOAD = {
    "ticker": "SPY",
    "name": "SPDR S&P 500 ETF",
    "asset_class": "etf",
    "sector": "Broad Market",
    "country": "US",
    "description": "Tracks the S&P 500 index.",
}


def create_indicator(client):
    return client.post("/api/v1/indicators", json=INDICATOR_PAYLOAD)


def create_asset(client):
    return client.post("/api/v1/assets", json=ASSET_PAYLOAD)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Indicator CRUD
# ---------------------------------------------------------------------------

def test_create_indicator_201(client):
    r = create_indicator(client)
    assert r.status_code == 201
    data = r.json()
    assert data["fred_series_id"] == "CPIAUCSL"
    assert data["id"] == 1


def test_create_indicator_duplicate_409(client):
    create_indicator(client)
    r = create_indicator(client)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_list_indicators(client):
    create_indicator(client)
    r = client.get("/api/v1/indicators")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_indicators_filter_by_category(client):
    create_indicator(client)
    r = client.get("/api/v1/indicators?category=inflation")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/indicators?category=gdp")
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_get_indicator_200(client):
    create_indicator(client)
    r = client.get("/api/v1/indicators/1")
    assert r.status_code == 200
    assert r.json()["fred_series_id"] == "CPIAUCSL"


def test_get_indicator_404(client):
    r = client.get("/api/v1/indicators/999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_update_indicator_200(client):
    create_indicator(client)
    r = client.patch("/api/v1/indicators/1", json={"description": "Updated description"})
    assert r.status_code == 200
    assert r.json()["description"] == "Updated description"


def test_update_indicator_404(client):
    r = client.patch("/api/v1/indicators/999", json={"description": "Nope"})
    assert r.status_code == 404


def test_delete_indicator_204(client):
    create_indicator(client)
    r = client.delete("/api/v1/indicators/1")
    assert r.status_code == 204

    # Confirm it's gone
    r = client.get("/api/v1/indicators/1")
    assert r.status_code == 404


def test_delete_indicator_404(client):
    r = client.delete("/api/v1/indicators/999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------

def test_create_asset_201(client):
    r = create_asset(client)
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == "SPY"
    assert data["id"] == 1


def test_create_asset_duplicate_409(client):
    create_asset(client)
    r = create_asset(client)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]


def test_list_assets(client):
    create_asset(client)
    r = client.get("/api/v1/assets")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_assets_filter_by_sector(client):
    create_asset(client)
    r = client.get("/api/v1/assets?sector=Broad Market")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.get("/api/v1/assets?sector=Energy")
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_get_asset_200(client):
    create_asset(client)
    r = client.get("/api/v1/assets/1")
    assert r.status_code == 200
    assert r.json()["ticker"] == "SPY"


def test_get_asset_404(client):
    r = client.get("/api/v1/assets/999")
    assert r.status_code == 404


def test_update_asset_200(client):
    create_asset(client)
    r = client.patch("/api/v1/assets/1", json={"sector": "Updated Sector"})
    assert r.status_code == 200
    assert r.json()["sector"] == "Updated Sector"


def test_update_asset_404(client):
    r = client.patch("/api/v1/assets/999", json={"sector": "Nope"})
    assert r.status_code == 404


def test_delete_asset_204(client):
    create_asset(client)
    r = client.delete("/api/v1/assets/1")
    assert r.status_code == 204

    r = client.get("/api/v1/assets/1")
    assert r.status_code == 404


def test_delete_asset_404(client):
    r = client.delete("/api/v1/assets/999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

def test_get_indicator_snapshots_empty(client):
    create_indicator(client)
    r = client.get("/api/v1/snapshots/indicators/1")
    assert r.status_code == 200
    assert r.json() == []


def test_get_indicator_snapshots_404(client):
    r = client.get("/api/v1/snapshots/indicators/999")
    assert r.status_code == 404


def test_get_asset_snapshots_empty(client):
    create_asset(client)
    r = client.get("/api/v1/snapshots/assets/1")
    assert r.status_code == 200
    assert r.json() == []


def test_get_asset_snapshots_404(client):
    r = client.get("/api/v1/snapshots/assets/999")
    assert r.status_code == 404


def test_ingest_indicator_404(client):
    r = client.post("/api/v1/snapshots/indicators/999/ingest")
    assert r.status_code == 404


def test_ingest_asset_404(client):
    r = client.post("/api/v1/snapshots/assets/999/ingest")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Analytics — insufficient data scenarios
# ---------------------------------------------------------------------------

def test_correlation_insufficient_data(client):
    create_indicator(client)
    create_asset(client)
    # No snapshots ingested — should return 422
    r = client.get("/api/v1/analytics/correlation?indicator_id=1&asset_id=1")
    assert r.status_code == 422


def test_correlation_indicator_not_found(client):
    create_asset(client)
    r = client.get("/api/v1/analytics/correlation?indicator_id=999&asset_id=1")
    assert r.status_code == 422


def test_correlation_asset_not_found(client):
    create_indicator(client)
    r = client.get("/api/v1/analytics/correlation?indicator_id=1&asset_id=999")
    assert r.status_code == 422


def test_recession_risk_no_data(client):
    # No indicators at all — should still return a valid response with 0 scores
    r = client.get("/api/v1/analytics/recession-risk")
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert "signals" in data
    assert data["score"] == 0.0


def test_macro_trend_no_data(client):
    create_indicator(client)
    r = client.get("/api/v1/analytics/macro-trend/1")
    assert r.status_code == 422


def test_macro_trend_indicator_not_found(client):
    r = client.get("/api/v1/analytics/macro-trend/999")
    assert r.status_code == 422


def test_sector_impact_no_indicator_data(client):
    create_indicator(client)
    r = client.get("/api/v1/analytics/sector-impact/1")
    assert r.status_code == 422


def test_market_summary_empty(client):
    # No indicators or assets — should return empty lists
    r = client.get("/api/v1/analytics/market-summary")
    assert r.status_code == 200
    data = r.json()
    assert data["indicators"] == []
    assert data["assets"] == []


def test_market_summary_with_data(client):
    create_indicator(client)
    create_asset(client)
    r = client.get("/api/v1/analytics/market-summary")
    assert r.status_code == 200
    data = r.json()
    assert len(data["indicators"]) == 1
    assert len(data["assets"]) == 1
    assert data["indicators"][0]["trend"] == "no_data"
    assert data["assets"][0]["trend"] == "no_data"