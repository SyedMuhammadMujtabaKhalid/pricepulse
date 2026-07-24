"""
PricePulse — SQLAlchemy ORM Models
===================================

Defines the database schema using SQLAlchemy 2.0 declarative models.

Engineering Decisions:
    1. UUID primary keys: Better for distributed systems and API endpoints.
    2. JSONB attributes: Electronics have varied specs (RAM vs Refresh Rate).
       JSONB provides NoSQL flexibility within a structured relational database.
    3. Type hints (Mapped[T]): SQLAlchemy 2.0 uses Python type hints for
       both static typing (mypy/pyright) and schema definition.
    4. String lengths are explicit (e.g., String(500)) for indexing efficiency.
    5. Constraints (UniqueConstraint, CheckConstraint) enforce data integrity
       at the database level, not just the application level.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Import the Base defined in database.py to avoid circular dependencies
from src.storage.database import Base


class Product(Base):
    """
    Core product entity being tracked.
    e.g., "Dell XPS 13"
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(200), index=True)
    url: Mapped[str | None] = mapped_column(String(1000))

    # Store flexible specs (RAM, storage, processor)
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )

    # Relationships
    prices: Mapped[list["PriceRecord"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    price_changes: Mapped[list["PriceChange"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Competitor(Base):
    """
    Data source or store being tracked.
    e.g., "Best Buy", "Amazon", "Newegg"
    """

    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), unique=True)
    domain: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50))  # api, scraper, csv
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('api', 'scraper', 'csv')", name="ck_competitor_source_type"
        ),
    )

    # Relationships
    prices: Mapped[list["PriceRecord"]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan"
    )


class PriceRecord(Base):
    """
    Append-only log of all price observations.
    We NEVER update rows here, only insert.
    """

    __tablename__ = "price_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"), index=True
    )

    # 12 digits total, 2 decimal places (up to $9,999,999,999.99)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
    source_run_id: Mapped[str | None] = mapped_column(String(100), index=True)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="prices")
    competitor: Mapped["Competitor"] = relationship(back_populates="prices")

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_price_positive"),
        # Prevent duplicate identical scrapes
        UniqueConstraint(
            "product_id", "competitor_id", "scraped_at", name="uq_price_observation"
        ),
        # Critical index for finding the "latest" price fast
        Index("idx_price_records_latest", "product_id", "competitor_id", "scraped_at"),
    )


class PriceChange(Base):
    """
    Materialized view of significant price changes.
    Pre-computed by the Intelligence Engine for fast dashboard queries.
    """

    __tablename__ = "price_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE")
    )

    old_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_diff: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pct_change: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    change_type: Mapped[str] = mapped_column(String(20))  # drop, increase
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="price_changes")

    __table_args__ = (
        CheckConstraint("change_type IN ('drop', 'increase')", name="ck_change_type"),
        Index("idx_price_changes_type_date", "change_type", "detected_at"),
    )


class Alert(Base):
    """
    System notifications generated from price changes.
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    price_change_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("price_changes.id", ondelete="SET NULL")
    )

    alert_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(1000))
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_alert_severity",
        ),
        Index("idx_alerts_unacked", "is_acknowledged", "created_at"),
    )


class PipelineRun(Base):
    """
    Audit log of data extraction jobs.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="running")

    records_extracted: Mapped[int] = mapped_column(default=0)
    records_validated: Mapped[int] = mapped_column(default=0)
    records_stored: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)

    error_details: Mapped[list[Any]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'failed')", name="ck_pipeline_status"
        ),
    )
