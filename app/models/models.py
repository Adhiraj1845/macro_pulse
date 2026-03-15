import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IndicatorCategory(str, enum.Enum):
    inflation = "inflation"
    interest_rate = "interest_rate"
    gdp = "gdp"
    unemployment = "unemployment"
    yield_curve = "yield_curve"
    credit = "credit"
    other = "other"


class AssetClass(str, enum.Enum):
    equity = "equity"
    etf = "etf"
    index = "index"
    commodity = "commodity"
    bond = "bond"
    other = "other"


# ---------------------------------------------------------------------------
# MacroIndicator
# ---------------------------------------------------------------------------


class MacroIndicator(Base):
    """
    Metadata for a macroeconomic indicator series sourced from FRED.
    One row per series (e.g. CPI, Fed Funds Rate).
    """

    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True, index=True)
    fred_series_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(IndicatorCategory), nullable=False)
    unit = Column(String(100), nullable=True)
    frequency = Column(String(50), nullable=True)  # e.g. "Monthly", "Quarterly"
    source = Column(String(100), nullable=False, default="FRED")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship to time-series observations
    snapshots = relationship(
        "IndicatorSnapshot", back_populates="indicator", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MacroIndicator {self.fred_series_id}: {self.name}>"


# ---------------------------------------------------------------------------
# IndicatorSnapshot
# ---------------------------------------------------------------------------


class IndicatorSnapshot(Base):
    """
    A single time-series observation for a MacroIndicator.
    Separated from indicator metadata to avoid data redundancy (2NF).
    """

    __tablename__ = "indicator_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    indicator_id = Column(
        Integer, ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to indicator
    indicator = relationship("MacroIndicator", back_populates="snapshots")

    # Composite index for fast date-range queries per indicator
    __table_args__ = (
        Index("ix_indicator_snapshots_indicator_date", "indicator_id", "date"),
        UniqueConstraint(
            "indicator_id", "date", name="uq_indicator_snapshot_date"
        ),
    )

    def __repr__(self):
        return f"<IndicatorSnapshot indicator_id={self.indicator_id} date={self.date} value={self.value}>"


# ---------------------------------------------------------------------------
# MarketAsset
# ---------------------------------------------------------------------------


class MarketAsset(Base):
    """
    Metadata for a financial market asset tracked via Yahoo Finance.
    One row per ticker (e.g. SPY, GLD, XLF).
    """

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    asset_class = Column(Enum(AssetClass), nullable=False)
    sector = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True, default="US")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship to price history
    snapshots = relationship(
        "AssetSnapshot", back_populates="asset", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MarketAsset {self.ticker}: {self.name}>"


# ---------------------------------------------------------------------------
# AssetSnapshot
# ---------------------------------------------------------------------------


class AssetSnapshot(Base):
    """
    Daily OHLCV price data for a MarketAsset.
    Separated from asset metadata to avoid data redundancy (2NF).
    """

    __tablename__ = "asset_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(
        Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=True)
    daily_return = Column(Float, nullable=True)  # (close - prev_close) / prev_close
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to asset
    asset = relationship("MarketAsset", back_populates="snapshots")

    # Composite index for fast date-range queries per asset
    __table_args__ = (
        Index("ix_asset_snapshots_asset_date", "asset_id", "date"),
        UniqueConstraint("asset_id", "date", name="uq_asset_snapshot_date"),
    )

    def __repr__(self):
        return f"<AssetSnapshot asset_id={self.asset_id} date={self.date} close={self.close}>"