from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import IndicatorCategory, MacroIndicator
from app.schemas import (
    IndicatorCreate,
    IndicatorResponse,
    IndicatorUpdate,
    IndicatorWithSnapshots,
)

router = APIRouter(prefix="/api/v1/indicators", tags=["Indicators"])


@router.get(
    "",
    response_model=list[IndicatorResponse],
    summary="List all indicators",
    description="Returns all tracked macroeconomic indicators. Optionally filter by category.",
)
def list_indicators(
    category: Optional[IndicatorCategory] = Query(
        None, description="Filter by indicator category"
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: Session = Depends(get_db),
):
    query = db.query(MacroIndicator)
    if category:
        query = query.filter(MacroIndicator.category == category)
    return query.offset(skip).limit(limit).all()


@router.get(
    "/{indicator_id}",
    response_model=IndicatorWithSnapshots,
    summary="Get indicator by ID",
    description="Returns a single macroeconomic indicator with its full time-series snapshot history.",
    responses={404: {"description": "Indicator not found"}},
)
def get_indicator(indicator_id: int, db: Session = Depends(get_db)):
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator with id {indicator_id} not found.",
        )
    return indicator


@router.post(
    "",
    response_model=IndicatorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new indicator",
    description="Adds a new macroeconomic indicator to the database. The FRED series ID must be unique.",
    responses={409: {"description": "Indicator with this FRED series ID already exists"}},
)
def create_indicator(payload: IndicatorCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(MacroIndicator)
        .filter(MacroIndicator.fred_series_id == payload.fred_series_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Indicator with FRED series ID '{payload.fred_series_id}' already exists.",
        )
    indicator = MacroIndicator(**payload.model_dump())
    db.add(indicator)
    db.commit()
    db.refresh(indicator)
    return indicator


@router.patch(
    "/{indicator_id}",
    response_model=IndicatorResponse,
    summary="Update an indicator",
    description="Partially updates an existing macroeconomic indicator. Only provided fields are updated.",
    responses={404: {"description": "Indicator not found"}},
)
def update_indicator(
    indicator_id: int, payload: IndicatorUpdate, db: Session = Depends(get_db)
):
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator with id {indicator_id} not found.",
        )
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(indicator, field, value)
    db.commit()
    db.refresh(indicator)
    return indicator


@router.delete(
    "/{indicator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an indicator",
    description="Permanently deletes an indicator and all its associated snapshots (cascade delete).",
    responses={404: {"description": "Indicator not found"}},
)
def delete_indicator(indicator_id: int, db: Session = Depends(get_db)):
    indicator = db.query(MacroIndicator).filter(MacroIndicator.id == indicator_id).first()
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indicator with id {indicator_id} not found.",
        )
    db.delete(indicator)
    db.commit()