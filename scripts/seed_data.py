"""
Seed Script
-----------
Populates the database with default macro indicators and market assets,
then triggers ingestion from FRED and Yahoo Finance for all of them.

Usage:
    python scripts/seed_data.py

Run this once after setting up the database. Safe to re-run —
existing records are skipped, and ingestion is idempotent.
"""

import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models.models import MacroIndicator, MarketAsset, IndicatorCategory, AssetClass
from app.services.ingestion import ingest_indicator_from_fred, ingest_asset_from_yfinance

# ---------------------------------------------------------------------------
# Default Indicators (FRED series)
# ---------------------------------------------------------------------------

DEFAULT_INDICATORS = [
    {
        "fred_series_id": "CPIAUCSL",
        "name": "Consumer Price Index (CPI)",
        "description": "CPI for all urban consumers, seasonally adjusted. Primary measure of inflation.",
        "category": IndicatorCategory.inflation,
        "unit": "Index 1982-84=100",
        "frequency": "Monthly",
        "source": "FRED",
    },
    {
        "fred_series_id": "FEDFUNDS",
        "name": "Federal Funds Rate",
        "description": "The interest rate at which banks lend to each other overnight. Primary monetary policy tool.",
        "category": IndicatorCategory.interest_rate,
        "unit": "Percent",
        "frequency": "Monthly",
        "source": "FRED",
    },
    {
        "fred_series_id": "UNRATE",
        "name": "Unemployment Rate",
        "description": "Percentage of the labour force that is unemployed and actively seeking work.",
        "category": IndicatorCategory.unemployment,
        "unit": "Percent",
        "frequency": "Monthly",
        "source": "FRED",
    },
    {
        "fred_series_id": "GDP",
        "name": "Gross Domestic Product (GDP)",
        "description": "Total monetary value of all goods and services produced in the US. Quarterly.",
        "category": IndicatorCategory.gdp,
        "unit": "Billions of Dollars",
        "frequency": "Quarterly",
        "source": "FRED",
    },
    {
        "fred_series_id": "T10Y2Y",
        "name": "10-Year minus 2-Year Treasury Spread",
        "description": "Yield curve spread. Inversion (negative value) is a leading recession indicator.",
        "category": IndicatorCategory.yield_curve,
        "unit": "Percent",
        "frequency": "Daily",
        "source": "FRED",
    },
    {
        "fred_series_id": "DGS10",
        "name": "10-Year Treasury Constant Maturity Rate",
        "description": "The yield on 10-year US government bonds. Benchmark for long-term interest rates.",
        "category": IndicatorCategory.interest_rate,
        "unit": "Percent",
        "frequency": "Daily",
        "source": "FRED",
    },
    {
        "fred_series_id": "PCEPI",
        "name": "PCE Price Index",
        "description": "Personal Consumption Expenditures Price Index. The Fed's preferred inflation measure.",
        "category": IndicatorCategory.inflation,
        "unit": "Index 2017=100",
        "frequency": "Monthly",
        "source": "FRED",
    },
]

# ---------------------------------------------------------------------------
# Default Assets (Yahoo Finance tickers)
# ---------------------------------------------------------------------------

DEFAULT_ASSETS = [
    # Broad market
    {"ticker": "SPY", "name": "SPDR S&P 500 ETF", "asset_class": AssetClass.etf, "sector": "Broad Market", "country": "US", "description": "Tracks the S&P 500 index."},
    {"ticker": "QQQ", "name": "Invesco QQQ Trust", "asset_class": AssetClass.etf, "sector": "Technology", "country": "US", "description": "Tracks the Nasdaq-100 index."},
    {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "asset_class": AssetClass.etf, "sector": "Small Cap", "country": "US", "description": "Tracks the Russell 2000 small-cap index."},
    # Sector ETFs
    {"ticker": "XLF", "name": "Financial Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Financials", "country": "US", "description": "Tracks US financial sector stocks."},
    {"ticker": "XLE", "name": "Energy Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Energy", "country": "US", "description": "Tracks US energy sector stocks."},
    {"ticker": "XLU", "name": "Utilities Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Utilities", "country": "US", "description": "Tracks US utilities sector stocks."},
    {"ticker": "XLRE", "name": "Real Estate Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Real Estate", "country": "US", "description": "Tracks US real estate sector stocks."},
    {"ticker": "XLK", "name": "Technology Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Technology", "country": "US", "description": "Tracks US technology sector stocks."},
    {"ticker": "XLP", "name": "Consumer Staples Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Consumer Staples", "country": "US", "description": "Tracks US consumer staples stocks."},
    {"ticker": "XLY", "name": "Consumer Discretionary Select Sector SPDR", "asset_class": AssetClass.etf, "sector": "Consumer Discretionary", "country": "US", "description": "Tracks US consumer discretionary stocks."},
    # Fixed income & alternatives
    {"ticker": "TLT", "name": "iShares 20+ Year Treasury Bond ETF", "asset_class": AssetClass.bond, "sector": "Fixed Income", "country": "US", "description": "Tracks long-duration US Treasury bonds."},
    {"ticker": "HYG", "name": "iShares iBoxx High Yield Corporate Bond ETF", "asset_class": AssetClass.bond, "sector": "Fixed Income", "country": "US", "description": "Tracks high yield (junk) corporate bonds."},
    {"ticker": "GLD", "name": "SPDR Gold Shares", "asset_class": AssetClass.commodity, "sector": "Commodities", "country": "US", "description": "Tracks the price of gold bullion."},
    {"ticker": "USO", "name": "United States Oil Fund", "asset_class": AssetClass.commodity, "sector": "Commodities", "country": "US", "description": "Tracks the price of West Texas Intermediate crude oil."},
]


# ---------------------------------------------------------------------------
# Seed Functions
# ---------------------------------------------------------------------------

def seed_indicators(db):
    print("\n📊 Seeding macro indicators...")
    created = 0
    skipped = 0
    indicator_ids = []

    for data in DEFAULT_INDICATORS:
        existing = db.query(MacroIndicator).filter(
            MacroIndicator.fred_series_id == data["fred_series_id"]
        ).first()

        if existing:
            print(f"  ⏭  {data['fred_series_id']} already exists — skipping")
            indicator_ids.append(existing.id)
            skipped += 1
        else:
            indicator = MacroIndicator(**data)
            db.add(indicator)
            db.commit()
            db.refresh(indicator)
            indicator_ids.append(indicator.id)
            print(f"  ✅ Created {data['fred_series_id']}: {data['name']}")
            created += 1

    print(f"\n  Created: {created} | Skipped: {skipped}")
    return indicator_ids


def seed_assets(db):
    print("\n📈 Seeding market assets...")
    created = 0
    skipped = 0
    asset_ids = []

    for data in DEFAULT_ASSETS:
        existing = db.query(MarketAsset).filter(
            MarketAsset.ticker == data["ticker"]
        ).first()

        if existing:
            print(f"  ⏭  {data['ticker']} already exists — skipping")
            asset_ids.append(existing.id)
            skipped += 1
        else:
            asset = MarketAsset(**data)
            db.add(asset)
            db.commit()
            db.refresh(asset)
            asset_ids.append(asset.id)
            print(f"  ✅ Created {data['ticker']}: {data['name']}")
            created += 1

    print(f"\n  Created: {created} | Skipped: {skipped}")
    return asset_ids


def ingest_all_indicators(db, indicator_ids):
    print("\n🔄 Ingesting indicator data from FRED...")
    print("  (This may take a minute — pulling full historical series)\n")

    for ind_id in indicator_ids:
        indicator = db.query(MacroIndicator).filter(MacroIndicator.id == ind_id).first()
        if not indicator:
            continue
        try:
            result = ingest_indicator_from_fred(indicator, db)
            print(f"  ✅ {indicator.fred_series_id}: {result['inserted']} inserted, {result['skipped']} skipped")
        except Exception as e:
            print(f"  ❌ {indicator.fred_series_id}: Failed — {e}")


def ingest_all_assets(db, asset_ids):
    print("\n🔄 Ingesting asset price data from Yahoo Finance...")
    print("  (This may take a minute — pulling full price history)\n")

    for asset_id in asset_ids:
        asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
        if not asset:
            continue
        try:
            result = ingest_asset_from_yfinance(asset, db)
            print(f"  ✅ {asset.ticker}: {result['inserted']} inserted, {result['skipped']} skipped")
        except Exception as e:
            print(f"  ❌ {asset.ticker}: Failed — {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  Macro Pulse — Database Seed Script")
    print("=" * 60)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        indicator_ids = seed_indicators(db)
        asset_ids = seed_assets(db)

        ingest = input("\n🌐 Ingest data from FRED and Yahoo Finance now? (y/n): ").strip().lower()
        if ingest == "y":
            ingest_all_indicators(db, indicator_ids)
            ingest_all_assets(db, asset_ids)
        else:
            print("\n  Skipped ingestion. Run ingestion manually via the API endpoints.")

        print("\n" + "=" * 60)
        print("  ✅ Seed complete! Run: uvicorn main:app --reload")
        print("=" * 60)

    finally:
        db.close()