"""
PricePulse — Main ETL Pipeline Runner
=====================================

Orchestrates the entire extraction, validation, and storage process.

Engineering Decisions:
    1. Pipeline acts as the conductor. It doesn't know *how* to scrape or validate,
       it just knows *when* to call those layers.
    2. Uses a PipelineRun model to record every execution for the dashboard's
       Pipeline Health page.
    3. Gracefully skips sources that fail, continuing with the rest, rather than
       crashing the whole pipeline.
"""

import asyncio
from datetime import datetime, timezone
import uuid
from typing import Any

from pydantic import ValidationError

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.logger import get_logger
from src.sources.base import BaseSource
from src.quality.validators import RawPriceRecord
from src.quality.dedup import deduplicate_records
from src.quality.anomaly import remove_anomalies
from src.storage.database import get_session
from src.storage.models import PipelineRun, Product, Competitor, PriceRecord

from src.engine.price_detector import PriceChangeDetector
from src.notifications.notifiers import BaseNotifier, ConsoleNotifier

log = get_logger(__name__)


class PipelineResult:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.extracted = 0
        self.validated = 0
        self.stored = 0
        self.errors = 0
        self.error_details: list[str] = []


class PricePulsePipeline:
    def __init__(self, sources: list[BaseSource], notifiers: list[BaseNotifier] | None = None):
        self.sources = sources
        self.notifiers = notifiers if notifiers is not None else [ConsoleNotifier()]
        self.run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def run(self) -> PipelineResult:
        """Execute the full ETL pipeline."""
        result = PipelineResult(self.run_id)
        
        # 1. Initialize PipelineRun in DB
        with get_session() as session:
            db_run = PipelineRun(run_id=self.run_id, status="running")
            session.add(db_run)
            session.commit()
            
        log.info("pipeline.started", run_id=self.run_id, sources=len(self.sources))

        try:
            # We process sources sequentially in the MVP to avoid overloading the DB or getting IP banned.
            # (In a V2, this could use asyncio.gather for parallel extraction)
            all_raw_data = []
            
            # --- EXTRACT ---
            for source in self.sources:
                try:
                    if await source.health_check():
                        raw_data = await source.extract()
                        # Tag each record with its origin source
                        for r in raw_data:
                            r.__dict__["_source_name"] = source.source_name
                            r.__dict__["_source_type"] = source.source_type
                        all_raw_data.extend(raw_data)
                        result.extracted += len(raw_data)
                    else:
                        msg = f"Source {source.source_name} failed health check. Skipping."
                        log.warning("pipeline.source.skipped", reason=msg)
                        result.errors += 1
                        result.error_details.append(msg)
                except ValidationError as e:
                    result.errors += 1
                    log.warning("pipeline.validation.failed", errors=e.errors())
                except Exception as e:
                    msg = f"Source {source.source_name} failed extraction: {str(e)}"
                    log.error("pipeline.source.failed", reason=msg)
                    result.errors += 1
                    result.error_details.append(msg)

            # --- VALIDATE & CLEAN ---
            validated_records: list[RawPriceRecord] = all_raw_data

            
            # Clean: Dedup + Anomalies
            cleaned = deduplicate_records(validated_records)
            cleaned = remove_anomalies(cleaned)
            result.validated = len(cleaned)

            # --- STORE ---
            if cleaned:
                result.stored = self._store_records(cleaned)
                
                # --- DETECT CHANGES & ALERT ---
                detector = PriceChangeDetector(self.notifiers)
                changes = detector.run(self.run_id)
                log.info("pipeline.detection.finished", changes=changes)
            else:
                log.warning("pipeline.store.skipped", reason="No valid records to store")

            # Update PipelineRun as Success
            self._finalize_run(result, status="success")
            return result

        except Exception as e:
            # Update PipelineRun as Failed
            log.error("pipeline.fatal", error=str(e), exc_info=True)
            result.errors += 1
            result.error_details.append(str(e))
            self._finalize_run(result, status="failed")
            raise

    def _store_records(self, records: list[RawPriceRecord]) -> int:
        """Upsert Products/Competitors, then insert PriceRecords using bulk/batch operations."""
        stored_count = 0
        
        with get_session() as session:
            # Batch size for PostgreSQL processing
            batch_size = 500
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                
                # We need to collect unique competitors and products to bulk upsert
                competitors_data = {}
                products_data = {}
                
                for record in batch:
                    c_name = record.__dict__["_source_name"]
                    if c_name not in competitors_data:
                        competitors_data[c_name] = {
                            "name": c_name,
                            "source_type": record.__dict__["_source_type"]
                        }
                    
                    if record.sku not in products_data:
                        products_data[record.sku] = {
                            "id": str(uuid.uuid4()),
                            "sku": record.sku,
                            "name": record.name,
                            "brand": record.brand,
                            "category": record.category,
                            "url": str(record.url) if record.url else None,
                            "attributes": record.attributes,
                            "updated_at": datetime.now(timezone.utc)
                        }

                # 1. Upsert Competitors
                if competitors_data:
                    stmt_c = pg_insert(Competitor).values(list(competitors_data.values()))
                    stmt_c = stmt_c.on_conflict_do_update(
                        index_elements=['name'],
                        set_={"source_type": stmt_c.excluded.source_type}
                    )
                    session.execute(stmt_c)

                # 2. Upsert Products
                if products_data:
                    stmt_p = pg_insert(Product).values(list(products_data.values()))
                    stmt_p = stmt_p.on_conflict_do_update(
                        index_elements=['sku'],
                        set_={
                            "name": stmt_p.excluded.name,
                            "brand": stmt_p.excluded.brand,
                            "category": stmt_p.excluded.category,
                            "url": stmt_p.excluded.url,
                            "attributes": stmt_p.excluded.attributes,
                            "updated_at": stmt_p.excluded.updated_at
                        }
                    )
                    session.execute(stmt_p)
                
                # Fetch mappings back to get IDs
                comp_names = list(competitors_data.keys())
                prod_skus = list(products_data.keys())
                
                db_comps = session.query(Competitor.id, Competitor.name).filter(Competitor.name.in_(comp_names)).all()
                comp_map = {c.name: c.id for c in db_comps}
                
                db_prods = session.query(Product.id, Product.sku).filter(Product.sku.in_(prod_skus)).all()
                prod_map = {p.sku: p.id for p in db_prods}

                # 3. Batch insert PriceRecords (Append only)
                price_records_data = []
                for record in batch:
                    price_records_data.append({
                        "product_id": prod_map[record.sku],
                        "competitor_id": comp_map[record.__dict__["_source_name"]],
                        "price": record.price,
                        "original_price": record.original_price,
                        "currency": record.currency,
                        "in_stock": record.in_stock,
                        "source_run_id": self.run_id
                    })

                if price_records_data:
                    # Use Insert On Conflict Do Nothing for idempotency
                    stmt_pr = pg_insert(PriceRecord).values(price_records_data)
                    stmt_pr = stmt_pr.on_conflict_do_nothing(
                        index_elements=['product_id', 'competitor_id', 'scraped_at']
                    )
                    session.execute(stmt_pr)
                    stored_count += len(price_records_data)

            session.commit()
            log.info("pipeline.store.success", count=stored_count)
            return stored_count

    def _finalize_run(self, result: PipelineResult, status: str) -> None:
        """Update the PipelineRun record in the database."""
        with get_session() as session:
            db_run = session.query(PipelineRun).filter_by(run_id=self.run_id).first()
            if db_run:
                db_run.status = status
                db_run.records_extracted = result.extracted
                db_run.records_validated = result.validated
                db_run.records_stored = result.stored
                db_run.errors = result.errors
                db_run.error_details = result.error_details
                db_run.completed_at = datetime.now(timezone.utc)
                session.commit()
