"""
Analytics Router
----------------
Five analytical endpoints that sit on top of the stored time-series data.
All heavy computation is delegated to app/services/analytics.py — this
router only handles HTTP concerns (parsing, validation, error handling).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analytics import (
    CorrelationResponse,
    MacroTrendResponse,
    MarketSummaryResponse,
    RecessionRiskResponse,
    SectorImpactResponse,
)
from app.services.analytics import (
    compute_correlation,
    compute_macro_trend,
    compute_market_summary,
    compute_recession_risk,
    compute_sector_impact,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get(
    "/correlation",
    response_model=CorrelationResponse,
    summary="Correlation analysis",
    description=(
        "Computes Pearson correlation between a macroeconomic indicator and a market asset. "
        "Both series are resampled to monthly frequency before alignment. "
        "Requires data to have been ingested for both the indicator and asset."
    ),
    responses={
        404: {"description": "Indicator or asset not found"},
        422: {"description": "Insufficient data for analysis"},
    },
)
def correlation(
    indicator_id: int = Query(..., description="ID of the macroeconomic indicator"),
    asset_id: int = Query(..., description="ID of the market asset"),
    start_date: Optional[date] = Query(None, description="Start of analysis window"),
    end_date: Optional[date] = Query(None, description="End of analysis window"),
    db: Session = Depends(get_db),
):
    try:
        return compute_correlation(indicator_id, asset_id, db, start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/recession-risk",
    response_model=RecessionRiskResponse,
    summary="Recession risk score",
    description=(
        "Computes a composite recession risk score (0–100) from four established "
        "macroeconomic signals: yield curve spread (T10Y2Y), unemployment rate (UNRATE), "
        "CPI inflation (CPIAUCSL), and the federal funds rate (FEDFUNDS). "
        "Signals are weighted by their relative predictive power in the academic literature. "
        "Ingest all four indicators for the most accurate score."
    ),
)
def recession_risk(db: Session = Depends(get_db)):
    try:
        return compute_recession_risk(db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/macro-trend/{indicator_id}",
    response_model=MacroTrendResponse,
    summary="Macro trend detection",
    description=(
        "Fits a linear regression to the last N observations of a macro indicator "
        "to determine trend direction (rising/falling/stable) and percentage change. "
        "The slope is normalised relative to the mean value for cross-indicator comparability."
    ),
    responses={
        404: {"description": "Indicator not found"},
        422: {"description": "Insufficient data for the requested number of periods"},
    },
)
def macro_trend(
    indicator_id: int,
    periods: int = Query(24, ge=3, le=120, description="Number of monthly periods to analyse"),
    db: Session = Depends(get_db),
):
    try:
        return compute_macro_trend(indicator_id, periods, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/sector-impact/{indicator_id}",
    response_model=SectorImpactResponse,
    summary="Sector impact analysis",
    description=(
        "Correlates a macro indicator against every tracked market asset, "
        "returning results sorted by absolute correlation strength. "
        "Assets with insufficient aligned data are excluded and counted separately. "
        "Use this to identify which sectors are most exposed to a given macro variable."
    ),
    responses={
        422: {"description": "No indicator data available"},
    },
)
def sector_impact(indicator_id: int, db: Session = Depends(get_db)):
    try:
        return compute_sector_impact(indicator_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/market-summary",
    response_model=MarketSummaryResponse,
    summary="Market summary",
    description=(
        "Returns the latest value, trend direction, and period-over-period change "
        "for every tracked indicator and asset. Designed to power the dashboard home page. "
        "Assets and indicators with no ingested data are included with null values."
    ),
)
def market_summary(db: Session = Depends(get_db)):
    try:
        return compute_market_summary(db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))