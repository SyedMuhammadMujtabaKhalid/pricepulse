"""
PricePulse — API Source Adapter
================================

Fetches data from structured JSON REST APIs using httpx.

Engineering Decisions:
    1. Uses `httpx` for async HTTP requests, which is much faster than `requests`
       when fetching from multiple sources concurrently.
    2. Enforces timeouts (10 seconds) to prevent the pipeline from hanging.
    3. Implements basic error handling for HTTP status codes.
"""

from typing import Any
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from src.core.logger import get_logger
from src.sources.base import BaseSource
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


class APISource(BaseSource):
    """Data source adapter for structured REST APIs."""

    def __init__(self, api_url: str, source_name: str, api_key: str | None = None) -> None:
        super().__init__()
        self.api_url = api_url
        self._source_name = source_name
        self.api_key = api_key
        
        # We configure a shared async client for connection pooling
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        self.client_kwargs = {
            "headers": headers,
            "timeout": httpx.Timeout(10.0),
        }

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def source_type(self) -> str:
        return "api"

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def extract(self, **kwargs: Any) -> list[RawPriceRecord]:
        """
        Extract data by calling the API.

        Handles common API response shapes:
          - Direct list: [{"sku": ..., "price": ...}, ...]
          - Nested under 'items': {"items": [...]}
          - Nested under 'products': {"products": [...]}  (DummyJSON format)
        """
        log.info("source.api.extract_started", source=self.source_name, url=self.api_url)
        
        try:
            async with httpx.AsyncClient(**self.client_kwargs) as client:
                response = await client.get(self.api_url, params=kwargs.get("params"))
                response.raise_for_status()
                
                data = response.json()
                
                # Support multiple common API response shapes
                if isinstance(data, list):
                    raw_records = data
                elif isinstance(data, dict):
                    raw_records = (
                        data.get("items")
                        or data.get("products")
                        or data.get("data")
                        or data.get("results")
                    )
                    if raw_records is None:
                        raise ValueError(
                            f"Cannot find product list in API response keys: {list(data.keys())}"
                        )
                else:
                    raise ValueError(f"Unexpected API response type: {type(data)}")
                
                if not isinstance(raw_records, list):
                    raise ValueError(f"Expected list from API, got {type(raw_records)}")
                
                # Map API fields to RawPriceRecord schema
                records = []
                for item in raw_records:
                    mapped = self._map_to_record(item)
                    if mapped:
                        records.append(mapped)
                
                log.info("source.api.extract_success", source=self.source_name, records=len(records))
                return records
                
        except httpx.HTTPStatusError as e:
            log.error(
                "source.api.http_error", 
                source=self.source_name, 
                status_code=e.response.status_code,
                detail=e.response.text
            )
            raise
        except Exception as e:
            log.error("source.api.extract_failed", source=self.source_name, error=str(e))
            raise

    def _map_to_record(self, item: dict) -> RawPriceRecord | None:
        """
        Map a raw API item dict to a RawPriceRecord.

        Handles field-name differences across common APIs:
          - DummyJSON uses 'title' for name, 'id' for sku, 'thumbnail' for url
          - Standard APIs might use 'name', 'sku', 'url' directly

        Returns None if the item cannot be mapped (logged as warning).
        """
        try:
            mapped = {
                "sku": str(item.get("sku") or item.get("id", "")),
                "name": item.get("name") or item.get("title", ""),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "url": item.get("url") or item.get("thumbnail"),
                "price": item.get("price", 0),
                "original_price": item.get("original_price"),
                "in_stock": item.get("in_stock", item.get("stock", 0) > 0)
                    if isinstance(item.get("stock"), (int, float))
                    else item.get("in_stock", True),
                "attributes": {
                    k: v for k, v in item.items()
                    if k not in ("sku", "id", "name", "title", "brand", "category",
                                 "url", "thumbnail", "price", "original_price",
                                 "in_stock", "stock", "images")
                },
            }
            return RawPriceRecord(**mapped)
        except Exception as e:
            log.warning(
                "source.api.map_failed",
                source=self.source_name,
                item_keys=list(item.keys()),
                error=str(e),
            )
            return None

    async def health_check(self) -> bool:
        """Verify the API is reachable (e.g., via an OPTIONS or HEAD request)."""
        try:
            async with httpx.AsyncClient(**self.client_kwargs) as client:
                # Some APIs don't like HEAD, but it's the standard way to check without pulling data
                response = await client.head(self.api_url)
                return response.status_code < 500
        except Exception as e:
            log.warning("source.api.health_failed", source=self.source_name, error=str(e))
            return False
