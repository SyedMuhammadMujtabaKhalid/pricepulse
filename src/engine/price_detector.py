"""
PricePulse — Price Change Detection Engine
==========================================

Analyzes newly inserted price records and detects significant price movements.

Engineering Decisions:
    1. Runs POST-extraction. We never modify extraction data; we compute diffs
       against the "last known" state stored in the DB.
    2. Materializes diffs into the `price_changes` table. This prevents the dashboard
       from having to run expensive window functions on millions of price records.
    3. Alert Generation is decoupled from Notification. This engine creates Alert
       records in the DB. A separate process (Phase 8/later) picks them up to email.
"""

from decimal import Decimal

from sqlalchemy import select, and_, desc

from src.core.logger import get_logger
from src.storage.database import get_session
from src.storage.models import PriceRecord, PriceChange, Alert
from src.notifications.notifiers import BaseNotifier, NotificationDispatcher

log = get_logger(__name__)


class PriceChangeDetector:
    def __init__(self, notifiers: list[BaseNotifier] | None = None):
        # We only care about drops > 5% for High alerts, > 15% for Critical.
        self.alert_threshold_pct = Decimal("5.0")
        self.dispatcher = NotificationDispatcher(notifiers or [])

    def run(self, run_id: str) -> int:
        """
        Analyze all price records inserted by a specific pipeline run.
        """
        log.info("engine.detection.started", run_id=run_id)
        changes_detected = 0
        alerts_generated = 0

        with get_session() as session:
            # Get all new price records from this run
            new_records = session.query(PriceRecord).filter_by(source_run_id=run_id).all()
            
            if not new_records:
                log.info("engine.detection.skipped", reason="No new records in this run")
                return 0

            for new_record in new_records:
                # Find the previous price for this exact product + competitor
                # (Ignoring the current one we just inserted)
                stmt = (
                    select(PriceRecord)
                    .where(
                        and_(
                            PriceRecord.product_id == new_record.product_id,
                            PriceRecord.competitor_id == new_record.competitor_id,
                            PriceRecord.id != new_record.id,
                        )
                    )
                    .order_by(desc(PriceRecord.scraped_at))
                    .limit(1)
                )
                prev_record = session.execute(stmt).scalar_one_or_none()

                if not prev_record:
                    # First time seeing this product at this competitor; no baseline to compare.
                    continue

                # Calculate diff
                old_price = prev_record.price
                new_price = new_record.price
                diff = new_price - old_price

                if diff == 0:
                    continue  # Price didn't change

                pct_change = (diff / old_price) * Decimal("100")
                
                change_type = "drop" if diff < 0 else "increase"

                # Materialize the change
                change = PriceChange(
                    product_id=new_record.product_id,
                    competitor_id=new_record.competitor_id,
                    old_price=old_price,
                    new_price=new_price,
                    price_diff=diff,
                    pct_change=pct_change,
                    change_type=change_type,
                )
                session.add(change)
                session.flush() # Flush to get change.id for the alert
                changes_detected += 1

                # Generate Alert if significant drop
                if change_type == "drop" and abs(pct_change) >= self.alert_threshold_pct:
                    severity = "critical" if abs(pct_change) >= Decimal("15.0") else "high"
                    
                    alert = Alert(
                        price_change_id=change.id,
                        alert_type="price_drop",
                        severity=severity,
                        message=f"PRICE DROP! Product ID {new_record.product_id} dropped by {abs(pct_change):.1f}% (now ${new_price})"
                    )
                    session.add(alert)
                    session.flush() # Flush to populate alert id before dispatching
                    self.dispatcher.dispatch(alert)
                    alerts_generated += 1

            session.commit()
            
        log.info("engine.detection.completed", changes=changes_detected, alerts=alerts_generated)
        return changes_detected
