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
import time

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models.models import MacroIndicator, MarketAsset, IndicatorCategory, AssetClass, AssetSnapshot, IndicatorSnapshot
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
    # ── Broad Market ETFs ──
    {"ticker": "SPY",  "name": "SPDR S&P 500 ETF",            "asset_class": AssetClass.etf,       "sector": "Broad Market",             "country": "US", "description": "Tracks the S&P 500 index."},
    {"ticker": "QQQ",  "name": "Invesco QQQ Trust",            "asset_class": AssetClass.etf,       "sector": "Technology",               "country": "US", "description": "Tracks the Nasdaq-100 index."},
    {"ticker": "IWM",  "name": "iShares Russell 2000 ETF",     "asset_class": AssetClass.etf,       "sector": "Small Cap",                "country": "US", "description": "Tracks the Russell 2000 small-cap index."},
    {"ticker": "DIA",  "name": "SPDR Dow Jones Industrial ETF","asset_class": AssetClass.etf,       "sector": "Broad Market",             "country": "US", "description": "Tracks the Dow Jones Industrial Average."},
    {"ticker": "VTI",  "name": "Vanguard Total Stock Market",  "asset_class": AssetClass.etf,       "sector": "Broad Market",             "country": "US", "description": "Tracks the total US stock market."},

    # ── SPDR Sector ETFs ──
    {"ticker": "XLF",  "name": "Financial Select Sector SPDR",          "asset_class": AssetClass.etf, "sector": "Financials",             "country": "US", "description": "Tracks US financial sector stocks."},
    {"ticker": "XLE",  "name": "Energy Select Sector SPDR",              "asset_class": AssetClass.etf, "sector": "Energy",                 "country": "US", "description": "Tracks US energy sector stocks."},
    {"ticker": "XLU",  "name": "Utilities Select Sector SPDR",           "asset_class": AssetClass.etf, "sector": "Utilities",              "country": "US", "description": "Tracks US utilities sector stocks."},
    {"ticker": "XLRE", "name": "Real Estate Select Sector SPDR",         "asset_class": AssetClass.etf, "sector": "Real Estate",            "country": "US", "description": "Tracks US real estate sector stocks."},
    {"ticker": "XLK",  "name": "Technology Select Sector SPDR",          "asset_class": AssetClass.etf, "sector": "Technology",             "country": "US", "description": "Tracks US technology sector stocks."},
    {"ticker": "XLP",  "name": "Consumer Staples Select Sector SPDR",    "asset_class": AssetClass.etf, "sector": "Consumer Staples",       "country": "US", "description": "Tracks US consumer staples stocks."},
    {"ticker": "XLY",  "name": "Consumer Discretionary Select Sector SPDR","asset_class": AssetClass.etf,"sector": "Consumer Discretionary","country": "US", "description": "Tracks US consumer discretionary stocks."},
    {"ticker": "XLV",  "name": "Health Care Select Sector SPDR",         "asset_class": AssetClass.etf, "sector": "Health Care",            "country": "US", "description": "Tracks US health care sector stocks."},
    {"ticker": "XLI",  "name": "Industrial Select Sector SPDR",          "asset_class": AssetClass.etf, "sector": "Industrials",            "country": "US", "description": "Tracks US industrial sector stocks."},
    {"ticker": "XLB",  "name": "Materials Select Sector SPDR",           "asset_class": AssetClass.etf, "sector": "Materials",              "country": "US", "description": "Tracks US materials sector stocks."},
    {"ticker": "XLC",  "name": "Communication Services Select Sector SPDR","asset_class": AssetClass.etf,"sector": "Communication Services","country": "US", "description": "Tracks US communication services stocks."},

    # ── Fixed Income ETFs ──
    {"ticker": "TLT",  "name": "iShares 20+ Year Treasury Bond ETF",     "asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Tracks long-duration US Treasury bonds."},
    {"ticker": "IEF",  "name": "iShares 7-10 Year Treasury Bond ETF",    "asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Tracks intermediate US Treasury bonds."},
    {"ticker": "SHY",  "name": "iShares 1-3 Year Treasury Bond ETF",     "asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Tracks short-term US Treasury bonds."},
    {"ticker": "LQD",  "name": "iShares Investment Grade Corporate Bond", "asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Tracks investment grade corporate bonds."},
    {"ticker": "HYG",  "name": "iShares iBoxx High Yield Corporate Bond","asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Tracks high yield (junk) corporate bonds."},
    {"ticker": "AGG",  "name": "iShares Core US Aggregate Bond ETF",     "asset_class": AssetClass.bond, "sector": "Fixed Income",          "country": "US", "description": "Broad US investment-grade bond market."},
    {"ticker": "EMB",  "name": "iShares JP Morgan USD Emerging Markets Bond","asset_class": AssetClass.bond,"sector": "Fixed Income",        "country": "US", "description": "Emerging market sovereign bonds in USD."},

    # ── Commodity ETFs ──
    {"ticker": "GLD",  "name": "SPDR Gold Shares",                       "asset_class": AssetClass.commodity, "sector": "Commodities",       "country": "US", "description": "Tracks the price of gold bullion."},
    {"ticker": "SLV",  "name": "iShares Silver Trust",                   "asset_class": AssetClass.commodity, "sector": "Commodities",       "country": "US", "description": "Tracks the price of silver."},
    {"ticker": "USO",  "name": "United States Oil Fund",                 "asset_class": AssetClass.commodity, "sector": "Commodities",       "country": "US", "description": "Tracks WTI crude oil futures."},
    {"ticker": "UNG",  "name": "United States Natural Gas Fund",         "asset_class": AssetClass.commodity, "sector": "Commodities",       "country": "US", "description": "Tracks natural gas futures prices."},
    {"ticker": "DBA",  "name": "Invesco DB Agriculture Fund",            "asset_class": AssetClass.commodity, "sector": "Commodities",       "country": "US", "description": "Tracks a basket of agricultural commodity futures."},
    {"ticker": "PDBC", "name": "Invesco Optimum Yield Diversified Commodity","asset_class": AssetClass.commodity,"sector": "Commodities",   "country": "US", "description": "Broad diversified commodity futures index."},

    # ── International ETFs ──
    {"ticker": "EFA",  "name": "iShares MSCI EAFE ETF",                  "asset_class": AssetClass.etf, "sector": "International Developed","country": "Intl", "description": "Developed market equities ex-US (Europe, Asia, Far East)."},
    {"ticker": "EEM",  "name": "iShares MSCI Emerging Markets ETF",      "asset_class": AssetClass.etf, "sector": "Emerging Markets",       "country": "Intl", "description": "Broad emerging markets equity exposure."},
    {"ticker": "FXI",  "name": "iShares China Large-Cap ETF",            "asset_class": AssetClass.etf, "sector": "Emerging Markets",       "country": "CN",   "description": "Large-cap Chinese equities (H-shares)."},
    {"ticker": "EWJ",  "name": "iShares MSCI Japan ETF",                 "asset_class": AssetClass.etf, "sector": "International Developed","country": "JP",   "description": "Tracks Japanese equities."},
    {"ticker": "EWG",  "name": "iShares MSCI Germany ETF",               "asset_class": AssetClass.etf, "sector": "International Developed","country": "DE",   "description": "Tracks German equities."},

    # ── S&P 500 Mega-Cap Equities ──
    # Technology
    {"ticker": "AAPL", "name": "Apple Inc.",                             "asset_class": AssetClass.equity, "sector": "Technology",           "country": "US", "description": "Consumer electronics, software & services."},
    {"ticker": "MSFT", "name": "Microsoft Corporation",                  "asset_class": AssetClass.equity, "sector": "Technology",           "country": "US", "description": "Cloud computing, enterprise software & OS."},
    {"ticker": "NVDA", "name": "NVIDIA Corporation",                     "asset_class": AssetClass.equity, "sector": "Technology",           "country": "US", "description": "GPUs, AI accelerators & data center chips."},
    {"ticker": "GOOGL","name": "Alphabet Inc. (Class A)",                "asset_class": AssetClass.equity, "sector": "Communication Services","country": "US", "description": "Google search, YouTube, cloud & AI."},
    {"ticker": "META", "name": "Meta Platforms Inc.",                    "asset_class": AssetClass.equity, "sector": "Communication Services","country": "US", "description": "Facebook, Instagram, WhatsApp & Reality Labs."},
    {"ticker": "AMZN", "name": "Amazon.com Inc.",                        "asset_class": AssetClass.equity, "sector": "Consumer Discretionary","country": "US", "description": "E-commerce, AWS cloud & digital advertising."},
    {"ticker": "TSLA", "name": "Tesla Inc.",                             "asset_class": AssetClass.equity, "sector": "Consumer Discretionary","country": "US", "description": "Electric vehicles, energy storage & solar."},
    {"ticker": "AVGO", "name": "Broadcom Inc.",                          "asset_class": AssetClass.equity, "sector": "Technology",           "country": "US", "description": "Semiconductors & infrastructure software."},
    # Financials
    {"ticker": "JPM",  "name": "JPMorgan Chase & Co.",                   "asset_class": AssetClass.equity, "sector": "Financials",           "country": "US", "description": "Largest US bank by assets."},
    {"ticker": "BAC",  "name": "Bank of America Corp.",                  "asset_class": AssetClass.equity, "sector": "Financials",           "country": "US", "description": "Retail & commercial banking, investment services."},
    {"ticker": "WFC",  "name": "Wells Fargo & Co.",                      "asset_class": AssetClass.equity, "sector": "Financials",           "country": "US", "description": "US retail & commercial bank."},
    {"ticker": "GS",   "name": "The Goldman Sachs Group Inc.",           "asset_class": AssetClass.equity, "sector": "Financials",           "country": "US", "description": "Investment banking & financial services."},
    {"ticker": "V",    "name": "Visa Inc.",                              "asset_class": AssetClass.equity, "sector": "Financials",           "country": "US", "description": "Global digital payments network."},
    # Health Care
    {"ticker": "UNH",  "name": "UnitedHealth Group Inc.",                "asset_class": AssetClass.equity, "sector": "Health Care",          "country": "US", "description": "Largest US managed health care company."},
    {"ticker": "JNJ",  "name": "Johnson & Johnson",                      "asset_class": AssetClass.equity, "sector": "Health Care",          "country": "US", "description": "Pharmaceuticals, medical devices & consumer health."},
    {"ticker": "LLY",  "name": "Eli Lilly and Company",                  "asset_class": AssetClass.equity, "sector": "Health Care",          "country": "US", "description": "Pharmaceuticals including GLP-1 weight-loss drugs."},
    {"ticker": "PFE",  "name": "Pfizer Inc.",                            "asset_class": AssetClass.equity, "sector": "Health Care",          "country": "US", "description": "Global pharmaceutical company."},
    # Consumer Staples
    {"ticker": "PG",   "name": "Procter & Gamble Co.",                   "asset_class": AssetClass.equity, "sector": "Consumer Staples",     "country": "US", "description": "Consumer goods — cleaning, personal care & health."},
    {"ticker": "KO",   "name": "The Coca-Cola Company",                  "asset_class": AssetClass.equity, "sector": "Consumer Staples",     "country": "US", "description": "Non-alcoholic beverages worldwide."},
    {"ticker": "WMT",  "name": "Walmart Inc.",                           "asset_class": AssetClass.equity, "sector": "Consumer Staples",     "country": "US", "description": "World's largest retailer by revenue."},
    # Energy
    {"ticker": "XOM",  "name": "Exxon Mobil Corporation",               "asset_class": AssetClass.equity, "sector": "Energy",               "country": "US", "description": "Integrated oil & gas supermajor."},
    {"ticker": "CVX",  "name": "Chevron Corporation",                    "asset_class": AssetClass.equity, "sector": "Energy",               "country": "US", "description": "Integrated energy company."},
    # Industrials
    {"ticker": "CAT",  "name": "Caterpillar Inc.",                       "asset_class": AssetClass.equity, "sector": "Industrials",          "country": "US", "description": "Construction & mining machinery."},
    {"ticker": "BA",   "name": "The Boeing Company",                     "asset_class": AssetClass.equity, "sector": "Industrials",          "country": "US", "description": "Commercial jets, defense & space systems."},
    # Consumer Discretionary
    {"ticker": "MCD",  "name": "McDonald's Corporation",                 "asset_class": AssetClass.equity, "sector": "Consumer Discretionary","country": "US", "description": "Global fast-food chain."},
    {"ticker": "NKE",  "name": "Nike Inc.",                              "asset_class": AssetClass.equity, "sector": "Consumer Discretionary","country": "US", "description": "Athletic footwear, apparel & equipment."},
    # Communication Services
    {"ticker": "NFLX", "name": "Netflix Inc.",                           "asset_class": AssetClass.equity, "sector": "Communication Services","country": "US", "description": "Streaming entertainment platform."},
    {"ticker": "DIS",  "name": "The Walt Disney Company",               "asset_class": AssetClass.equity, "sector": "Communication Services","country": "US", "description": "Entertainment, streaming & theme parks."},
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
    """
    Batch-downloads all new assets via yf.download() — a single HTTP request
    for all tickers instead of one per ticker, which avoids Yahoo Finance rate limits.
    Assets that already have snapshot data are skipped entirely.
    """
    import yfinance as yf
    import pandas as pd
    from datetime import date as date_type

    print("\n🔄 Ingesting asset price data from Yahoo Finance...")

    # Split into already-ingested (skip) and new (download)
    assets_to_ingest = []
    for asset_id in asset_ids:
        asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
        if not asset:
            continue
        existing = db.query(AssetSnapshot).filter(AssetSnapshot.asset_id == asset_id).count()
        if existing > 0:
            print(f"  ⏭  {asset.ticker}: {existing} records already exist — skipping")
        else:
            assets_to_ingest.append(asset)

    if not assets_to_ingest:
        print("\n  All assets already have price data.\n")
        return

    tickers = [a.ticker for a in assets_to_ingest]
    print(f"\n  Batch-downloading {len(tickers)} new tickers in one request...\n")

    try:
        raw = yf.download(tickers, period="max", auto_adjust=True, progress=True)
    except Exception as e:
        print(f"\n  ❌ Batch download failed: {e}")
        print("  Wait a few minutes for the Yahoo Finance rate limit to reset, then re-run.")
        return

    if raw.empty:
        print("\n  ❌ No data returned. Yahoo Finance may be rate-limiting this IP.")
        print("  Wait ~5 minutes and re-run the script.")
        return

    # Extract per-ticker DataFrame from the MultiIndex result
    def get_ticker_df(raw, ticker):
        if not isinstance(raw.columns, pd.MultiIndex):
            # Single ticker — raw IS the ticker DataFrame
            return raw
        try:
            return raw.xs(ticker, level="Ticker", axis=1)
        except KeyError:
            try:
                return raw.xs(ticker, level=1, axis=1)
            except KeyError:
                return pd.DataFrame()

    print()
    for asset in assets_to_ingest:
        hist = get_ticker_df(raw, asset.ticker)
        if hist.empty or "Close" not in hist.columns:
            print(f"  ❌ {asset.ticker}: No data in batch response")
            continue

        hist = hist.dropna(subset=["Close"])
        hist["daily_return"] = hist["Close"].pct_change()

        inserted = 0
        for obs_date, row in hist.iterrows():
            obs_date_py = obs_date.date() if hasattr(obs_date, "date") else obs_date
            daily_return = float(row["daily_return"]) if pd.notna(row.get("daily_return")) else None
            snapshot = AssetSnapshot(
                asset_id=asset.id,
                date=obs_date_py,
                open=float(row["Open"]) if pd.notna(row.get("Open")) else None,
                high=float(row["High"]) if pd.notna(row.get("High")) else None,
                low=float(row["Low"]) if pd.notna(row.get("Low")) else None,
                close=float(row["Close"]),
                volume=int(row["Volume"]) if pd.notna(row.get("Volume")) else None,
                daily_return=daily_return,
            )
            db.add(snapshot)
            inserted += 1

        db.commit()
        print(f"  ✅ {asset.ticker}: {inserted} records inserted")


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