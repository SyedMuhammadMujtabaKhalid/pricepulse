import pytest
from decimal import Decimal
from pydantic import ValidationError
from src.quality.validators import RawPriceRecord

def test_valid_record():
    record = RawPriceRecord(sku="SKU123", name="Test Laptop", price=Decimal("999.99"), category="laptop")
    assert record.sku == "SKU123"
    assert record.price == Decimal("999.99")
    assert record.in_stock is True

def test_negative_price_fails():
    with pytest.raises(ValidationError):
        RawPriceRecord(sku="SKU123", name="Test Laptop", price=-10.0)

def test_sku_normalization():
    record = RawPriceRecord(sku=" sku123  ", name="Test Laptop", price=999.99)
    assert record.sku == "SKU123"
