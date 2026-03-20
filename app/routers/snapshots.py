"""
Snapshots Router
----------------
Endpoints for triggering data ingestion from external sources (FRED, Yahoo Finance)
and for querying stored time-series snapshots directly.

Ingestion endpoints are POST because they trigger a side effect
(writing data to the database), even though they don't take a request body.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AssetSnapshot, IndicatorSnapshot, MacroIndicator, MarketAsset
from app.schemas import (
    AssetIngestResponse,
    AssetSnapshotResponse,
    IngestResponse,
    SnapshotResponse,
)
from app.services.ingestion import ingest_asset_from_yfinance, ingest_indicator_from_fred

router = APIRouter(prefix="/api/v1/snapshots", tags=["Snapshots & Ingestion"])

# Ingest endpoints get a tighter limit — each call hits an external API (FRED / Yahoo Finance)
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Indicator Snapshots
# ---------------------------------------------------------------------------


@router.post(
    "/indicators/{indicator_id}/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest indicator data from FRED",
    description=(
        "Pulls the full observation history for the given indicator from the FRED API "
        "and stores any new observations in the database. Safe to call repeatedly — "
        "already-existing dates are skipped automatically."
    ),
    responses={
        404: {"description": "Indicator not found"},
        422: {"description": "FRED API key not configured or invalid series ID"},
    },
)
@limiter.limit("10/minute")
def ingest_indicator(request: Request, indicator_id: int, db: Session = Depends(get_db)):
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator with id {indicator_id} not found.",
        )
    try:
        result = ingest_indicator_from_fred(indicator, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"FRED API error: {str(e)}",
        )
    return result


@router.get(
    "/indicators/{indicator_id}",
    response_model=list[SnapshotResponse],
    summary="Get indicator snapshots",
    description="Returns time-series observations for an indicator, with optional date range filtering.",
    responses={404: {"description": "Indicator not found"}},
)
def get_indicator_snapshots(
    indicator_id: int,
    start_date: Optional[date] = Query(None, description="Filter from this date (inclusive)"),
    end_date: Optional[date] = Query(None, description="Filter to this date (inclusive)"),
    limit: int = Query(500, ge=1, le=5000, description="Maximum records to return"),
    db: Session = Depends(get_db),
):
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator with id {indicator_id} not found.",
        )

    query = (
        db.query(IndicatorSnapshot)
        .filter(IndicatorSnapshot.indicator_id == indicator_id)
        .order_by(IndicatorSnapshot.date.asc())
    )

    if start_date:
        query = query.filter(IndicatorSnapshot.date >= start_date)
    if end_date:
        query = query.filter(IndicatorSnapshot.date <= end_date)

    return query.limit(limit).all()


# ---------------------------------------------------------------------------
# Asset Snapshots
# ---------------------------------------------------------------------------


@router.post(
    "/assets/{asset_id}/ingest",
    response_model=AssetIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest asset price data from Yahoo Finance",
    description=(
        "Pulls the full OHLCV price history for the given asset from Yahoo Finance "
        "and stores any new records in the database. Daily returns are computed automatically. "
        "Safe to call repeatedly — already-existing dates are skipped."
    ),
    responses={
        404: {"description": "Asset not found"},
        422: {"description": "Invalid ticker or no data returned"},
    },
)
@limiter.limit("10/minute")
def ingest_asset(request: Request, asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with id {asset_id} not found.",
        )
    try:
        result = ingest_asset_from_yfinance(asset, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Yahoo Finance error: {str(e)}",
        )
    return result


@router.get(
    "/assets/{asset_id}",
    response_model=list[AssetSnapshotResponse],
    summary="Get asset price snapshots",
    description="Returns OHLCV price history for an asset, with optional date range filtering.",
    responses={404: {"description": "Asset not found"}},
)
def get_asset_snapshots(
    asset_id: int,
    start_date: Optional[date] = Query(None, description="Filter from this date (inclusive)"),
    end_date: Optional[date] = Query(None, description="Filter to this date (inclusive)"),
    limit: int = Query(500, ge=1, le=5000, description="Maximum records to return"),
    db: Session = Depends(get_db),
):
    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with id {asset_id} not found.",
        )

    query = (
        db.query(AssetSnapshot)
        .filter(AssetSnapshot.asset_id == asset_id)
        .order_by(AssetSnapshot.date.asc())
    )

    if start_date:
        query = query.filter(AssetSnapshot.date >= start_date)
    if end_date:
        query = query.filter(AssetSnapshot.date <= end_date)

    return query.limit(limit).all()