"""
Ingestion Service
-----------------
Handles pulling data from external sources (FRED API, Yahoo Finance)
and storing it in the local database.

Design decisions:
- Idempotent: safe to call multiple times — skips rows that already exist
- Returns inserted/skipped counts so the caller knows what happened
- FRED data fetched via the fredapi library (wraps the FRED REST API)
- Market data fetched via yfinance (wraps Yahoo Finance)
- Daily returns computed as (close - prev_close) / prev_close
"""

from datetime import date

import pandas as pd
from fredapi import Fred
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import AssetSnapshot, IndicatorSnapshot, MacroIndicator, MarketAsset


# ---------------------------------------------------------------------------
# FRED Ingestion
# ---------------------------------------------------------------------------


def ingest_indicator_from_fred(indicator: MacroIndicator, db: Session) -> dict:
    """
    Pulls the full observation history for a FRED series and stores
    any new observations in the database.

    Returns a dict with inserted/skipped counts.
    """
    if not settings.fred_api_key:
        raise ValueError(
            "FRED_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
        )

    fred = Fred(api_key=settings.fred_api_key)

    # Pull the full series from FRED
    series: pd.Series = fred.get_series(indicator.fred_series_id)

    # Drop NaN values (FRED sometimes has gaps)
    series = series.dropna()

    # Fetch existing dates for this indicator to avoid duplicates
    existing_dates = {
        row.date
        for row in db.query(IndicatorSnapshot.date)
        .filter(IndicatorSnapshot.indicator_id == indicator.id)
        .all()
    }

    inserted = 0
    skipped = 0

    for obs_date, value in series.items():
        # pandas Timestamp → Python date
        obs_date_py: date = obs_date.date() if hasattr(obs_date, "date") else obs_date

        if obs_date_py in existing_dates:
            skipped += 1
            continue

        snapshot = IndicatorSnapshot(
            indicator_id=indicator.id,
            date=obs_date_py,
            value=float(value),
        )
        db.add(snapshot)
        inserted += 1

    db.commit()

    return {
        "indicator_id": indicator.id,
        "fred_series_id": indicator.fred_series_id,
        "inserted": inserted,
        "skipped": skipped,
        "message": f"Ingestion complete. {inserted} new observations added, {skipped} already existed.",
    }


# ---------------------------------------------------------------------------
# Yahoo Finance Ingestion
# ---------------------------------------------------------------------------


def ingest_asset_from_yfinance(asset: MarketAsset, db: Session) -> dict:
    """
    Pulls the full price history for a ticker from Yahoo Finance and
    stores any new OHLCV rows in the database.

    Daily returns are computed from the close price series:
        daily_return = (close_t - close_{t-1}) / close_{t-1}

    Returns a dict with inserted/skipped counts.
    """
    import time
    import yfinance as yf

    ticker = yf.Ticker(asset.ticker)

    # Pull max available history with retry on rate-limit (429)
    # Waits: 5s, 10s, 20s, 40s — Yahoo Finance needs longer back-off than typical APIs
    hist: pd.DataFrame = pd.DataFrame()
    last_exc: Exception = Exception("unknown error")
    for attempt in range(4):
        try:
            hist = ticker.history(period="max", auto_adjust=True)
            if not hist.empty:
                break
            # yfinance returns empty silently when rate-limited; retry with back-off
            time.sleep(5 * (2 ** attempt))
        except Exception as e:
            last_exc = e
            err = str(e).lower()
            if "429" in err or "rate" in err or "too many" in err:
                time.sleep(5 * (2 ** attempt))  # 5s, 10s, 20s, 40s
            else:
                raise

    if hist.empty:
        raise ValueError(
            f"No data returned from Yahoo Finance for ticker '{asset.ticker}'. "
            "Check the ticker symbol is valid."
        )

    # Compute daily returns (percentage change, first row will be NaN → None)
    hist["daily_return"] = hist["Close"].pct_change()

    # Fetch existing dates for this asset to avoid duplicates
    existing_dates = {
        row.date
        for row in db.query(AssetSnapshot.date)
        .filter(AssetSnapshot.asset_id == asset.id)
        .all()
    }

    inserted = 0
    skipped = 0

    for obs_date, row in hist.iterrows():
        # pandas Timestamp → Python date
        obs_date_py: date = obs_date.date() if hasattr(obs_date, "date") else obs_date

        if obs_date_py in existing_dates:
            skipped += 1
            continue

        # daily_return is NaN for first row — store as None
        daily_return = None
        if pd.notna(row.get("daily_return")):
            daily_return = float(row["daily_return"])

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

    return {
        "asset_id": asset.id,
        "ticker": asset.ticker,
        "inserted": inserted,
        "skipped": skipped,
        "message": f"Ingestion complete. {inserted} new price records added, {skipped} already existed.",
    }