"""
PricePulse — FastAPI REST API Layer
====================================

Exposes decoupled HTTP endpoints for products, price history, price drops, and alerts.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Any
from datetime import datetime

from src.storage.database import get_session
from src.storage.models import Product, PriceRecord, PriceChange, Alert, PipelineRun

app = FastAPI(
    title="PricePulse Intelligence Platform API",
    description="REST API for accessing competitor price tracking, historical observations, and alert feeds.",
    version="1.0.0"
)


class ProductOut(BaseModel):
    id: str
    sku: str
    name: str
    brand: str
    category: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class PriceRecordOut(BaseModel):
    id: str
    product_id: str
    price: float
    original_price: float
    scraped_at: datetime
    source_run_id: str

    class Config:
        from_attributes = True


class PriceChangeOut(BaseModel):
    id: str
    product_id: str
    old_price: float
    new_price: float
    price_diff: float
    pct_change: float
    change_type: str
    detected_at: datetime

    class Config:
        from_attributes = True


class AlertOut(BaseModel):
    id: str
    price_change_id: str
    alert_type: str
    severity: str
    message: str
    is_acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "pricepulse-api"}


@app.get("/api/v1/products", response_model=list[ProductOut])
def list_products(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Retrieve list of tracked products."""
    with get_session() as session:
        products = session.query(Product).order_by(Product.created_at.desc()).limit(limit).all()
        return [
            ProductOut(
                id=str(p.id),
                sku=p.sku,
                name=p.name,
                brand=p.brand,
                category=p.category,
                url=p.url,
                created_at=p.created_at
            )
            for p in products
        ]


@app.get("/api/v1/products/{sku}/history", response_model=list[PriceRecordOut])
def get_price_history(sku: str) -> Any:
    """Retrieve historical price observations for a given SKU."""
    with get_session() as session:
        product = session.query(Product).filter_by(sku=sku).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with SKU '{sku}' not found")

        records = (
            session.query(PriceRecord)
            .filter_by(product_id=product.id)
            .order_by(PriceRecord.scraped_at.asc())
            .all()
        )
        return [
            PriceRecordOut(
                id=str(r.id),
                product_id=str(r.product_id),
                price=float(r.price),
                original_price=float(r.original_price),
                scraped_at=r.scraped_at,
                source_run_id=r.source_run_id
            )
            for r in records
        ]


@app.get("/api/v1/changes", response_model=list[PriceChangeOut])
def list_price_changes(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Retrieve recent price changes across all products."""
    with get_session() as session:
        changes = session.query(PriceChange).order_by(PriceChange.detected_at.desc()).limit(limit).all()
        return [
            PriceChangeOut(
                id=str(c.id),
                product_id=str(c.product_id),
                old_price=float(c.old_price),
                new_price=float(c.new_price),
                price_diff=float(c.price_diff),
                pct_change=float(c.pct_change),
                change_type=c.change_type,
                detected_at=c.detected_at
            )
            for c in changes
        ]


@app.get("/api/v1/alerts", response_model=list[AlertOut])
def list_alerts(limit: int = Query(50, ge=1, le=200)) -> Any:
    """Retrieve recent alerts."""
    with get_session() as session:
        alerts = session.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
        return [
            AlertOut(
                id=str(a.id),
                price_change_id=str(a.price_change_id),
                alert_type=a.alert_type,
                severity=a.severity,
                message=a.message,
                is_acknowledged=a.is_acknowledged,
                created_at=a.created_at
            )
            for a in alerts
        ]
