"""
Analytics Service
-----------------
All mathematical and statistical logic for the five analytics endpoints.

Design decisions:
- Uses pandas for time-series alignment and resampling (monthly frequency)
- Pearson correlation via scipy.stats for statistical rigour
- Linear regression via numpy.polyfit for trend detection
- Recession risk uses a weighted composite of four established economic signals
- All functions return plain dicts matching the analytics schemas
- Service layer is kept pure — no FastAPI imports, no HTTP concerns
"""

from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session

from app.models.models import AssetSnapshot, IndicatorSnapshot, MacroIndicator, MarketAsset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_indicator_series(indicator_id: int, db: Session) -> pd.Series:
    """
    Loads all snapshots for an indicator into a pandas Series
    indexed by date, resampled to month-end frequency.
    Monthly resampling is necessary because FRED macro data is monthly
    but we need to align it with daily asset price data.
    """
    rows = (
        db.query(IndicatorSnapshot)
        .filter(IndicatorSnapshot.indicator_id == indicator_id)
        .order_by(IndicatorSnapshot.date.asc())
        .all()
    )
    if not rows:
        return pd.Series(dtype=float)

    series = pd.Series(
        {row.date: row.value for row in rows}
    )
    series.index = pd.to_datetime(series.index)
    # Resample to month-end, forward-fill gaps (e.g. quarterly GDP)
    return series.resample("ME").last().ffill()


def _get_asset_series(asset_id: int, db: Session) -> pd.Series:
    """
    Loads close prices for an asset into a pandas Series,
    resampled to month-end to align with indicator data.
    """
    rows = (
        db.query(AssetSnapshot)
        .filter(AssetSnapshot.asset_id == asset_id)
        .order_by(AssetSnapshot.date.asc())
        .all()
    )
    if not rows:
        return pd.Series(dtype=float)

    series = pd.Series(
        {row.date: row.close for row in rows}
    )
    series.index = pd.to_datetime(series.index)
    return series.resample("ME").last().ffill()


def _interpret_correlation(r: float) -> str:
    """Maps a Pearson r value to a plain English interpretation."""
    abs_r = abs(r)
    direction = "positive" if r >= 0 else "negative"
    if abs_r >= 0.8:
        strength = "Very strong"
    elif abs_r >= 0.6:
        strength = "Strong"
    elif abs_r >= 0.4:
        strength = "Moderate"
    elif abs_r >= 0.2:
        strength = "Weak"
    else:
        strength = "Very weak or no"
    return f"{strength} {direction} correlation"


# ---------------------------------------------------------------------------
# 1. Correlation Analysis
# ---------------------------------------------------------------------------


def compute_correlation(
    indicator_id: int,
    asset_id: int,
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Computes Pearson correlation between a macro indicator and a market asset.
    Both series are resampled to monthly frequency before alignment.
    Raises ValueError if insufficient data for meaningful analysis.
    """
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise ValueError(f"Indicator with id {indicator_id} not found.")

    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise ValueError(f"Asset with id {asset_id} not found.")

    ind_series = _get_indicator_series(indicator_id, db)
    asset_series = _get_asset_series(asset_id, db)

    if ind_series.empty or asset_series.empty:
        raise ValueError(
            "Insufficient data. Ingest data for both the indicator and asset before running correlation."
        )

    # Align both series on shared dates
    df = pd.DataFrame({"indicator": ind_series, "asset": asset_series}).dropna()

    # Apply date filters if provided
    if start_date:
        df = df[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df.index <= pd.Timestamp(end_date)]

    if len(df) < 6:
        raise ValueError(
            f"Only {len(df)} aligned data points found. Need at least 6 for meaningful correlation."
        )

    r, _ = stats.pearsonr(df["indicator"], df["asset"])

    series_points = [
        {
            "date": idx.date(),
            "indicator_value": row["indicator"],
            "asset_value": row["asset"],
        }
        for idx, row in df.iterrows()
    ]

    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator.name,
        "asset_id": asset_id,
        "asset_ticker": asset.ticker,
        "correlation": round(r, 4),
        "interpretation": _interpret_correlation(r),
        "data_points": len(df),
        "start_date": df.index.min().date(),
        "end_date": df.index.max().date(),
        "series": series_points,
    }


# ---------------------------------------------------------------------------
# 2. Recession Risk Score
# ---------------------------------------------------------------------------

# Signal definitions — each maps a FRED series to a scoring function
# Weights sum to 1.0, based on relative predictive power in the literature
RECESSION_SIGNALS = [
    {
        "name": "Yield Curve (10Y–2Y)",
        "fred_series_id": "T10Y2Y",
        "weight": 0.35,
        "description": "Inverted yield curve (negative spread) is the strongest single recession predictor.",
    },
    {
        "name": "Unemployment Rate",
        "fred_series_id": "UNRATE",
        "weight": 0.25,
        "description": "Rising unemployment signals economic contraction. Uses Sahm Rule logic.",
    },
    {
        "name": "Consumer Price Index",
        "fred_series_id": "CPIAUCSL",
        "weight": 0.20,
        "description": "Extreme inflation erodes purchasing power and often precedes Fed tightening cycles.",
    },
    {
        "name": "Federal Funds Rate",
        "fred_series_id": "FEDFUNDS",
        "weight": 0.20,
        "description": "Rapid rate hikes historically precede recessions by tightening credit conditions.",
    },
]


def _score_yield_curve(value: float) -> float:
    """
    Yield curve (T10Y2Y): only scores when actually inverted (negative).
    0.0 at flat/positive, scales linearly to 1.0 at -2.0 inversion.
    """
    if value <= -2.0:
        return 1.0
    elif value < 0.0:
        return abs(value) / 2.0
    return 0.0


def _score_unemployment(values: pd.Series) -> float:
    """
    Sahm Rule inspired: score rises when unemployment increases
    relative to its recent 12-month low.
    """
    if len(values) < 13:
        return 0.0
    recent = values.iloc[-13:]
    current = recent.iloc[-1]
    twelve_month_low = recent.min()
    rise = current - twelve_month_low
    # Sahm threshold is 0.5pp — score linearly from 0 to 1 over 0–1.0pp rise
    return min(1.0, rise / 1.0)


def _score_cpi(values: pd.Series) -> float:
    """
    CPI YoY change: high inflation (>6%) or deflation (<0%) both signal stress.
    """
    if len(values) < 13:
        return 0.0
    yoy_change = (values.iloc[-1] - values.iloc[-13]) / values.iloc[-13] * 100
    if yoy_change >= 6.0:
        return min(1.0, (yoy_change - 3.0) / 6.0)
    elif yoy_change < 0.0:
        return min(1.0, abs(yoy_change) / 3.0)
    return 0.0


def _score_fed_funds(values: pd.Series) -> float:
    """
    Fed funds rate: rapid rises over 12 months signal tightening risk.
    A rise of 3pp+ over 12 months scores 1.0.
    """
    if len(values) < 13:
        return 0.0
    change = values.iloc[-1] - values.iloc[-13]
    if change <= 0:
        return 0.0
    return min(1.0, change / 3.0)


def compute_recession_risk(db: Session) -> dict:
    """
    Computes a composite recession risk score (0–100) from four
    established macroeconomic signals.
    """
    scoring_functions = {
        "T10Y2Y": _score_yield_curve,
        "UNRATE": _score_unemployment,
        "CPIAUCSL": _score_cpi,
        "FEDFUNDS": _score_fed_funds,
    }

    signals = []
    composite_score = 0.0
    as_of_date = None

    for signal_def in RECESSION_SIGNALS:
        fred_id = signal_def["fred_series_id"]

        indicator = (
            db.query(MacroIndicator)
            .filter(MacroIndicator.fred_series_id == fred_id)
            .first()
        )

        if not indicator:
            signals.append({
                "name": signal_def["name"],
                "fred_series_id": fred_id,
                "current_value": None,
                "signal_score": 0.0,
                "weight": signal_def["weight"],
                "contribution": 0.0,
                "interpretation": f"{fred_id} not yet ingested. Add and ingest this indicator to include it.",
            })
            continue

        series = _get_indicator_series(indicator.id, db)

        if series.empty:
            signals.append({
                "name": signal_def["name"],
                "fred_series_id": fred_id,
                "current_value": None,
                "signal_score": 0.0,
                "weight": signal_def["weight"],
                "contribution": 0.0,
                "interpretation": "No data available. Run ingestion for this indicator.",
            })
            continue

        current_value = float(series.iloc[-1])
        # Use actual snapshot date, not the resampled month-end date
        latest_snap = (
            db.query(IndicatorSnapshot)
            .filter(IndicatorSnapshot.indicator_id == indicator.id)
            .order_by(IndicatorSnapshot.date.desc())
            .first()
        )
        latest_date = latest_snap.date if latest_snap else series.index[-1].date()

        if as_of_date is None or latest_date > as_of_date:
            as_of_date = latest_date

        # Score each signal using its specific function
        scorer = scoring_functions[fred_id]
        if fred_id == "T10Y2Y":
            signal_score = scorer(current_value)
        else:
            signal_score = scorer(series)

        contribution = signal_score * signal_def["weight"] * 100
        composite_score += contribution

        signals.append({
            "name": signal_def["name"],
            "fred_series_id": fred_id,
            "current_value": round(current_value, 4),
            "signal_score": round(signal_score, 4),
            "weight": signal_def["weight"],
            "contribution": round(contribution, 2),
            "interpretation": signal_def["description"],
        })

    # Determine risk level and colour
    score = round(composite_score, 1)
    if score < 25:
        level, color = "Low", "green"
        summary = "Macro indicators are broadly healthy. No significant recession signals detected."
    elif score < 50:
        level, color = "Elevated", "amber"
        summary = "Some warning signals present. Economic conditions warrant monitoring."
    elif score < 75:
        level, color = "High", "red"
        summary = "Multiple recession indicators are elevated. Significant contraction risk."
    else:
        level, color = "Critical", "critical"
        summary = "Severe recession signals across multiple indicators. High probability of contraction."

    return {
        "score": score,
        "level": level,
        "color": color,
        "summary": summary,
        "signals": signals,
        "as_of_date": as_of_date,
    }


# ---------------------------------------------------------------------------
# 3. Macro Trend Detection
# ---------------------------------------------------------------------------


def compute_macro_trend(indicator_id: int, periods: int, db: Session) -> dict:
    """
    Fits a linear regression to the last N observations of an indicator
    to determine trend direction and magnitude.

    Direction thresholds (normalised slope):
    - rising:  slope > +0.001
    - falling: slope < -0.001
    - stable:  between -0.001 and +0.001
    """
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise ValueError(f"Indicator with id {indicator_id} not found.")

    series = _get_indicator_series(indicator_id, db)

    if series.empty:
        raise ValueError("No data available. Run ingestion for this indicator first.")

    if len(series) < periods:
        raise ValueError(
            f"Requested {periods} periods but only {len(series)} observations available."
        )

    subset = series.iloc[-periods:]
    x = np.arange(len(subset))
    y = subset.values.astype(float)

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # Normalise slope relative to mean value for cross-indicator comparability
    mean_val = np.mean(y)
    norm_slope = slope / mean_val if mean_val != 0 else slope

    if norm_slope > 0.001:
        direction = "rising"
    elif norm_slope < -0.001:
        direction = "falling"
    else:
        direction = "stable"

    earliest_value = float(subset.iloc[0])
    latest_value = float(subset.iloc[-1])
    change_pct = ((latest_value - earliest_value) / earliest_value * 100) if earliest_value != 0 else 0.0

    interpretation = (
        f"{indicator.name} is {direction} over the last {periods} periods, "
        f"with a {abs(change_pct):.2f}% {'increase' if change_pct >= 0 else 'decrease'} "
        f"from {earliest_value:.2f} to {latest_value:.2f}."
    )

    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator.name,
        "fred_series_id": indicator.fred_series_id,
        "periods": periods,
        "direction": direction,
        "change_pct": round(change_pct, 4),
        "latest_value": round(latest_value, 4),
        "earliest_value": round(earliest_value, 4),
        "latest_date": subset.index[-1].date(),
        "earliest_date": subset.index[0].date(),
        "slope": round(float(slope), 6),
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# 4. Sector Impact Analysis
# ---------------------------------------------------------------------------


def compute_sector_impact(indicator_id: int, db: Session) -> dict:
    """
    Correlates a macro indicator against every tracked asset,
    then groups and sorts results by absolute correlation descending.

    Assets with fewer than 6 aligned data points are excluded and counted
    in insufficient_data_assets.
    """
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise ValueError(f"Indicator with id {indicator_id} not found.")

    ind_series = _get_indicator_series(indicator_id, db)
    if ind_series.empty:
        raise ValueError("No indicator data available. Run ingestion first.")

    assets = db.query(MarketAsset).all()

    results = []
    insufficient = 0

    for asset in assets:
        asset_series = _get_asset_series(asset.id, db)
        if asset_series.empty:
            insufficient += 1
            continue

        df = pd.DataFrame({"indicator": ind_series, "asset": asset_series}).dropna()

        if len(df) < 6:
            insufficient += 1
            continue

        r, _ = stats.pearsonr(df["indicator"], df["asset"])

        results.append({
            "asset_id": asset.id,
            "ticker": asset.ticker,
            "asset_name": asset.name,
            "sector": asset.sector,
            "asset_class": asset.asset_class.value,
            "correlation": round(r, 4),
            "data_points": len(df),
            "interpretation": _interpret_correlation(r),
        })

    # Sort by absolute correlation descending
    results.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "indicator_id": indicator_id,
        "indicator_name": indicator.name,
        "fred_series_id": indicator.fred_series_id,
        "results": results,
        "total_assets_analysed": len(results),
        "insufficient_data_assets": insufficient,
    }


# ---------------------------------------------------------------------------
# 5. Market Summary
# ---------------------------------------------------------------------------


def compute_market_summary(db: Session) -> dict:
    """
    Returns the latest value and trend direction for every tracked
    indicator and asset. Designed to power the dashboard home page.
    """
    indicators = db.query(MacroIndicator).all()
    assets = db.query(MarketAsset).all()

    indicator_summaries = []
    for ind in indicators:
        snapshots = (
            db.query(IndicatorSnapshot)
            .filter(IndicatorSnapshot.indicator_id == ind.id)
            .order_by(IndicatorSnapshot.date.desc())
            .limit(2)
            .all()
        )

        if not snapshots:
            indicator_summaries.append({
                "id": ind.id,
                "fred_series_id": ind.fred_series_id,
                "name": ind.name,
                "category": ind.category.value,
                "latest_value": None,
                "latest_date": None,
                "previous_value": None,
                "change": None,
                "change_pct": None,
                "trend": "no_data",
            })
            continue

        latest = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None
        change = round(latest.value - previous.value, 4) if previous else None
        change_pct = round((change / previous.value) * 100, 4) if (change is not None and previous.value != 0) else None

        if change is None:
            trend = "flat"
        elif change > 0:
            trend = "up"
        elif change < 0:
            trend = "down"
        else:
            trend = "flat"

        indicator_summaries.append({
            "id": ind.id,
            "fred_series_id": ind.fred_series_id,
            "name": ind.name,
            "category": ind.category.value,
            "latest_value": round(latest.value, 4),
            "latest_date": latest.date,
            "previous_value": round(previous.value, 4) if previous else None,
            "change": change,
            "change_pct": change_pct,
            "trend": trend,
        })

    asset_summaries = []
    for asset in assets:
        snapshots = (
            db.query(AssetSnapshot)
            .filter(AssetSnapshot.asset_id == asset.id)
            .order_by(AssetSnapshot.date.desc())
            .limit(2)
            .all()
        )

        if not snapshots:
            asset_summaries.append({
                "id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class.value,
                "sector": asset.sector,
                "latest_close": None,
                "latest_date": None,
                "daily_return": None,
                "trend": "no_data",
            })
            continue

        latest = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None

        if latest.daily_return is None:
            trend = "flat"
        elif latest.daily_return > 0:
            trend = "up"
        elif latest.daily_return < 0:
            trend = "down"
        else:
            trend = "flat"

        asset_summaries.append({
            "id": asset.id,
            "ticker": asset.ticker,
            "name": asset.name,
            "asset_class": asset.asset_class.value,
            "sector": asset.sector,
            "latest_close": round(latest.close, 4),
            "latest_date": latest.date,
            "daily_return": round(latest.daily_return, 6) if latest.daily_return else None,
            "trend": trend,
        })

    return {
        "indicators": indicator_summaries,
        "assets": asset_summaries,
        "as_of": datetime.utcnow().isoformat(),
    }