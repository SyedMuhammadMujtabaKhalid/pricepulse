"""
PricePulse — Data Quality Validators
====================================

Pydantic schemas for validating raw data from sources.

Engineering Decisions:
    1. Pydantic v2: Used for blazing fast, type-safe validation before data
       ever touches the database.
    2. Strict constraints: Prices must be >= 0. SKUs cannot be empty.
    3. Normalization: URLs and SKUs are stripped of whitespace and standardized
       during validation via field_validator.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RawPriceRecord(BaseModel):
    """
    Schema for a single price observation from any source.
    All data adapters (CSV, API, Scraper) must return dictionaries
    that conform to this schema.
    """
    
    sku: str = Field(..., min_length=1, max_length=100, description="Unique product identifier")
    name: str = Field(..., min_length=1, max_length=500, description="Product display name")
    brand: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=200)
    url: HttpUrl | str | None = Field(None, description="Source URL")
    
    price: Decimal = Field(..., ge=0, description="Current selling price")
    original_price: Decimal | None = Field(None, ge=0, description="List/MSRP price if discounted")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    in_stock: bool = Field(default=True)
    
    attributes: dict[str, Any] = Field(default_factory=dict, description="Flexible JSON specs")

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        """Ensure SKUs are uppercase and stripped of whitespace."""
        return v.strip().upper()

    @field_validator("name", "brand", "category")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        """Clean up messy text from scrapers."""
        return v.strip() if v else None
        
    @field_validator("url")
    @classmethod
    def url_to_string(cls, v: HttpUrl | str | None) -> str | None:
        """Pydantic v2 parses HttpUrl into an object; we want a string for the DB."""
        if v is None:
            return None
        return str(v)

    @field_validator("original_price")
    @classmethod
    def original_price_makes_sense(cls, v: Decimal | None, info: Any) -> Decimal | None:
        """If original_price is provided, it shouldn't be less than the selling price."""
        if v is not None and "price" in info.data:
            selling_price = info.data["price"]
            # If original_price is somehow lower, trust the selling price
            if v < selling_price:
                return None
        return v


class ValidationResult(BaseModel):
    """Result of validating a batch of records."""
    valid_records: list[RawPriceRecord]
    invalid_count: int
    errors: list[dict[str, Any]]
