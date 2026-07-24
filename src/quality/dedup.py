"""
PricePulse — Deduplication Engine
=================================

Removes duplicate records extracted from the same source run.

Engineering Decisions:
    1. Sources sometimes paginate poorly or list the same product in multiple categories.
       If a source returns the same SKU twice in one run, we must deduplicate before
       inserting into the DB, otherwise the unique constraint (sku, competitor_id, scraped_at)
       might throw an error or we just waste DB space.
    2. Conflict Resolution: If duplicates exist, we keep the lowest price.
"""

from src.core.logger import get_logger
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


def deduplicate_records(records: list[RawPriceRecord]) -> list[RawPriceRecord]:
    """
    Deduplicate a list of validated records based on SKU.
    If multiple records have the same SKU, keeps the one with the lowest price.
    """
    if not records:
        return []

    unique_records: dict[str, RawPriceRecord] = {}
    dupe_count = 0

    for record in records:
        sku = record.sku
        if sku in unique_records:
            dupe_count += 1
            # Keep the lowest price
            if record.price < unique_records[sku].price:
                unique_records[sku] = record
        else:
            unique_records[sku] = record

    if dupe_count > 0:
        log.info(
            "quality.dedup.removed",
            duplicates_removed=dupe_count,
            final_count=len(unique_records),
        )

    return list(unique_records.values())
