from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import IndicatorCategory


# ---------------------------------------------------------------------------
# Indicator Schemas
# ---------------------------------------------------------------------------


class IndicatorBase(BaseModel):
    fred_series_id: str = Field(..., max_length=50, examples=["CPIAUCSL"])
    name: str = Field(..., max_length=200, examples=["Consumer Price Index"])
    description: Optional[str] = Field(None, examples=["CPI for all urban consumers"])
    category: IndicatorCategory = Field(..., examples=["inflation"])
    unit: Optional[str] = Field(None, max_length=100, examples=["Index 1982-84=100"])
    frequency: Optional[str] = Field(None, max_length=50, examples=["Monthly"])
    source: str = Field("FRED", max_length=100)


class IndicatorCreate(IndicatorBase):
    pass


class IndicatorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    category: Optional[IndicatorCategory] = None
    unit: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=50)
    source: Optional[str] = Field(None, max_length=100)


class IndicatorResponse(IndicatorBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Snapshot Schemas
# ---------------------------------------------------------------------------


class SnapshotBase(BaseModel):
    date: date
    value: float


class SnapshotCreate(SnapshotBase):
    pass


class SnapshotResponse(SnapshotBase):
    id: int
    indicator_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class IndicatorWithSnapshots(IndicatorResponse):
    snapshots: list[SnapshotResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Ingest Response
# ---------------------------------------------------------------------------


class IngestResponse(BaseModel):
    indicator_id: int
    fred_series_id: str
    inserted: int
    skipped: int
    message: str