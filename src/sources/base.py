"""
PricePulse — Source Interface
=============================

Abstract Base Class for all data sources.

Engineering Decisions:
    1. Pluggable Architecture: By forcing all sources to implement this interface,
       the extraction layer doesn't care if data comes from an API, scraper, or CSV.
    2. Pydantic return types: Sources return dictionaries that match Pydantic schemas,
       which will be formally validated in the Quality Layer (Phase 4).
    3. Error isolation: Individual sources catch their own transient errors, but
       propagate fatal ones.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.quality.validators import RawPriceRecord

class BaseSource(ABC):
    """
    Abstract interface for all data extraction sources.
    Every new data source must inherit from this and implement its methods.
    """

    def __init__(self) -> None:
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable identifier for logging (e.g., 'amazon_scraper')"""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type of source: 'api', 'scraper', or 'csv'"""
        pass

    @abstractmethod
    async def extract(self, **kwargs: Any) -> list[RawPriceRecord]:
        """
        Extract raw data from the source.
        
        Returns:
            A list of validated RawPriceRecord models.
            
        Raises:
            Exception: If extraction fundamentally fails.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify the source is reachable/readable.
        Used by the monitoring layer.
        """
        pass
