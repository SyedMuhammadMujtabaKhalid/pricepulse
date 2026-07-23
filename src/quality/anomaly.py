"""
PricePulse — Anomaly Detection
===============================

Sanity checks to prevent garbage data from entering the database.

Engineering Decisions:
    1. Scrapers can break when site layouts change (e.g., extracting "0.99" from
       a shipping cost instead of a "$999.00" laptop price).
    2. Anomaly detection catches these extreme outliers before they trigger
       false alerts or ruin analytics.
"""

from decimal import Decimal

from sqlalchemy import select

from src.core.logger import get_logger
from src.quality.validators import RawPriceRecord
from src.storage.database import get_session
from src.storage.models import Product, PriceRecord

log = get_logger(__name__)

# Configurable thresholds
CATEGORY_BOUNDS = {
    "laptop": {"min": Decimal("100"), "max": Decimal("5000")}
}
MAX_PRICE_DROP_PCT = Decimal("0.50")
MAX_PRICE_INC_PCT = Decimal("1.00")

def remove_anomalies(records: list[RawPriceRecord]) -> list[RawPriceRecord]:
    """
    Filter out records with clearly impossible prices or extreme price jumps.
    """
    clean_records = []
    anomaly_count = 0
    
    # Fetch latest prices for all SKUs in the batch to check for extreme jumps
    skus = [r.sku for r in records]
    latest_prices = {}
    
    with get_session() as session:
        # Get the most recent price for each product
        # For simplicity, we just take the last recorded price across any competitor for the product
        stmt = (
            select(Product.sku, PriceRecord.price)
            .join(PriceRecord, Product.id == PriceRecord.product_id)
            .order_by(Product.sku, PriceRecord.scraped_at.desc())
        )
        
        # We need to distinct on sku. In PostgreSQL we can use distinct(Product.sku)
        stmt = stmt.distinct(Product.sku)
        
        try:
            results = session.execute(stmt).all()
            for sku, price in results:
                latest_prices[sku] = price
        except Exception as e:
            log.error("quality.anomaly.db_error", error=str(e))
            # If DB fails, we still want to apply static bounds

    for record in records:
        last_price = latest_prices.get(record.sku)
        
        if _is_anomaly(record, last_price):
            anomaly_count += 1
            log.warning(
                "quality.anomaly.dropped",
                sku=record.sku,
                price=float(record.price),
                name=record.name,
                reason="Failed sanity check or exceeded change threshold"
            )
        else:
            clean_records.append(record)

    if anomaly_count > 0:
        log.info("quality.anomaly.summary", anomalies_removed=anomaly_count, final_count=len(clean_records))

    return clean_records

def _is_anomaly(record: RawPriceRecord, last_price: Decimal | None = None) -> bool:
    """
    Business rules for anomaly detection.
    """
    price = record.price
    cat = (record.category or "").lower()

    # Rule 1: Category Bounds
    bounds = CATEGORY_BOUNDS.get(cat)
    if bounds:
        if price < bounds["min"] or price > bounds["max"]:
            return True

    # Rule 2: Price Change Thresholds
    if last_price and last_price > Decimal("0"):
        diff = price - last_price
        pct_change = diff / last_price
        
        if pct_change < -MAX_PRICE_DROP_PCT:
            return True
        if pct_change > MAX_PRICE_INC_PCT:
            return True

    return False

