from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import AssetClass


# ---------------------------------------------------------------------------
# Asset Schemas
# ---------------------------------------------------------------------------


class AssetBase(BaseModel):
    ticker: str = Field(..., max_length=20, examples=["SPY"])
    name: str = Field(..., max_length=200, examples=["SPDR S&P 500 ETF Trust"])
    asset_class: AssetClass = Field(..., examples=["etf"])
    sector: Optional[str] = Field(None, max_length=100, examples=["Broad Market"])
    country: Optional[str] = Field("US", max_length=100)
    description: Optional[str] = Field(None, examples=["Tracks the S&P 500 index"])


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    asset_class: Optional[AssetClass] = None
    sector: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Asset Snapshot Schemas
# ---------------------------------------------------------------------------


class AssetSnapshotBase(BaseModel):
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
    daily_return: Optional[float] = None


class AssetSnapshotCreate(AssetSnapshotBase):
    pass


class AssetSnapshotResponse(AssetSnapshotBase):
    id: int
    asset_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetWithSnapshots(AssetResponse):
    snapshots: list[AssetSnapshotResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ingest Response
# ---------------------------------------------------------------------------


class AssetIngestResponse(BaseModel):
    asset_id: int
    ticker: str
    inserted: int
    skipped: int
    message: str