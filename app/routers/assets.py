from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AssetClass, MarketAsset
from app.schemas import (
    AssetCreate,
    AssetResponse,
    AssetUpdate,
    AssetWithSnapshots,
)

router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])


@router.get(
    "",
    response_model=list[AssetResponse],
    summary="List all assets",
    description="Returns all tracked market assets. Optionally filter by sector, asset class, or country.",
)
def list_assets(
    sector: Optional[str] = Query(None, description="Filter by sector (e.g. Technology)"),
    asset_class: Optional[AssetClass] = Query(None, description="Filter by asset class"),
    country: Optional[str] = Query(None, description="Filter by country (e.g. US)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: Session = Depends(get_db),
):
    query = db.query(MarketAsset)
    if sector:
        query = query.filter(MarketAsset.sector == sector)
    if asset_class:
        query = query.filter(MarketAsset.asset_class == asset_class)
    if country:
        query = query.filter(MarketAsset.country == country)
    return query.offset(skip).limit(limit).all()


@router.get(
    "/{asset_id}",
    response_model=AssetWithSnapshots,
    summary="Get asset by ID",
    description="Returns a single market asset with its full OHLCV price snapshot history.",
    responses={404: {"description": "Asset not found"}},
)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with id {asset_id} not found.",
        )
    return asset


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new asset",
    description="Adds a new market asset to the database. The ticker symbol must be unique.",
    responses={409: {"description": "Asset with this ticker already exists"}},
)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(MarketAsset)
        .filter(MarketAsset.ticker == payload.ticker.upper())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset with ticker '{payload.ticker.upper()}' already exists.",
        )
    asset = MarketAsset(**payload.model_dump())
    asset.ticker = asset.ticker.upper()
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update an asset",
    description="Partially updates an existing market asset. Only provided fields are updated.",
    responses={404: {"description": "Asset not found"}},
)
def update_asset(asset_id: int, payload: AssetUpdate, db: Session = Depends(get_db)):
    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with id {asset_id} not found.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an asset",
    description="Permanently deletes an asset and all its associated price snapshots (cascade delete).",
    responses={404: {"description": "Asset not found"}},
)
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(MarketAsset).filter(MarketAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with id {asset_id} not found.",
        )
    db.delete(asset)
    db.commit()