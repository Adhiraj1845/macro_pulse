"""
Analytics Schemas
-----------------
Response models for all five analytics endpoints.
Kept separate from indicator/asset schemas to keep files focused.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


class CorrelationPoint(BaseModel):
    """A single aligned data point used in correlation analysis."""
    date: date
    indicator_value: float
    asset_value: float


class CorrelationResponse(BaseModel):
    indicator_id: int
    indicator_name: str
    asset_id: int
    asset_ticker: str
    correlation: float
    interpretation: str          # Plain English e.g. "Strong negative correlation"
    data_points: int             # Number of aligned monthly observations used
    start_date: Optional[date]
    end_date: Optional[date]
    series: list[CorrelationPoint]


# ---------------------------------------------------------------------------
# Recession Risk
# ---------------------------------------------------------------------------


class RecessionSignal(BaseModel):
    """Individual signal contribution to the composite recession risk score."""
    name: str                    # e.g. "Yield Curve (T10Y2Y)"
    fred_series_id: str
    current_value: Optional[float]
    signal_score: float          # 0.0 – 1.0
    weight: float                # Weight in composite score
    contribution: float          # signal_score * weight * 100
    interpretation: str          # Plain English explanation of this signal


class RecessionRiskResponse(BaseModel):
    score: float                 # 0 – 100 composite score
    level: str                   # "Low" | "Elevated" | "High" | "Critical"
    color: str                   # "green" | "amber" | "red" | "critical"
    summary: str                 # Plain English summary
    signals: list[RecessionSignal]
    as_of_date: Optional[date]   # Date of most recent data used


# ---------------------------------------------------------------------------
# Macro Trend
# ---------------------------------------------------------------------------


class MacroTrendResponse(BaseModel):
    indicator_id: int
    indicator_name: str
    fred_series_id: str
    periods: int                 # Number of periods analysed
    direction: str               # "rising" | "falling" | "stable"
    change_pct: float            # Percentage change over the period
    latest_value: Optional[float]
    earliest_value: Optional[float]
    latest_date: Optional[date]
    earliest_date: Optional[date]
    slope: float                 # Linear regression slope (normalised)
    interpretation: str


# ---------------------------------------------------------------------------
# Sector Impact
# ---------------------------------------------------------------------------


class SectorCorrelation(BaseModel):
    asset_id: int
    ticker: str
    asset_name: str
    sector: Optional[str]
    asset_class: str
    correlation: float
    data_points: int
    interpretation: str


class SectorImpactResponse(BaseModel):
    indicator_id: int
    indicator_name: str
    fred_series_id: str
    results: list[SectorCorrelation]   # Sorted by absolute correlation descending
    total_assets_analysed: int
    insufficient_data_assets: int


# ---------------------------------------------------------------------------
# Market Summary
# ---------------------------------------------------------------------------


class IndicatorSummary(BaseModel):
    id: int
    fred_series_id: str
    name: str
    category: str
    latest_value: Optional[float]
    latest_date: Optional[date]
    previous_value: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    trend: str                   # "up" | "down" | "flat" | "no_data"


class AssetSummary(BaseModel):
    id: int
    ticker: str
    name: str
    asset_class: str
    sector: Optional[str]
    latest_close: Optional[float]
    latest_date: Optional[date]
    daily_return: Optional[float]
    trend: str                   # "up" | "down" | "flat" | "no_data"


class MarketSummaryResponse(BaseModel):
    indicators: list[IndicatorSummary]
    assets: list[AssetSummary]
    as_of: str                   # ISO timestamp of when summary was generated