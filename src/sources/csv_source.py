"""
PricePulse — CSV Source Adapter
================================

Imports historical or static data from CSV files.

Engineering Decisions:
    1. Uses built-in `csv` module for simple files, keeping Pandas out of the
       extraction pipeline to minimize memory overhead.
    2. Maps CSV headers directly to our expected data schema.
"""

import csv
import os
from pathlib import Path
from typing import Any

from src.core.logger import get_logger
from src.sources.base import BaseSource
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


class CSVSource(BaseSource):
    """Data source adapter for local CSV files."""

    def __init__(self, file_path: str | Path) -> None:
        super().__init__()
        self.file_path = Path(file_path)

    @property
    def source_name(self) -> str:
        return f"csv_import_{self.file_path.name}"

    @property
    def source_type(self) -> str:
        return "csv"

    async def extract(self, **kwargs: Any) -> list[RawPriceRecord]:
        """
        Extract data by reading the CSV file.
        Expects columns: sku, name, brand, category, url, price, original_price, in_stock
        """
        log.info("source.csv.extract_started", file=str(self.file_path))
        
        if not await self.health_check():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        records: list[RawPriceRecord] = []
        try:
            # Synchronous file reading (acceptable for local CSV processing in MVP)
            with open(self.file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up data slightly before yielding
                    record_dict = {
                        "sku": row.get("sku", "").strip(),
                        "name": row.get("name", "").strip(),
                        "brand": row.get("brand", "").strip(),
                        "category": row.get("category", "").strip(),
                        "url": row.get("url", "").strip(),
                        "price": row.get("price"),
                        "original_price": row.get("original_price") or None,
                        "in_stock": str(row.get("in_stock", "true")).lower() in ("true", "1", "yes"),
                        "attributes": {},  # CSV doesn't easily store nested JSON
                    }
                    records.append(RawPriceRecord(**record_dict))
                    
            log.info("source.csv.extract_success", records=len(records))
            return records
            
        except Exception as e:
            log.error("source.csv.extract_failed", error=str(e), file=str(self.file_path))
            raise

    async def health_check(self) -> bool:
        """Verify the CSV file exists and is readable."""
        exists = self.file_path.exists() and self.file_path.is_file()
        if not exists:
            log.warning("source.csv.health_failed", file=str(self.file_path))
        return exists
