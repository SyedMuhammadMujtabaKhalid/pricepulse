import pytest
from decimal import Decimal
from src.quality.validators import RawPriceRecord
from src.sources.csv_source import CSVSource
import tempfile
import os

@pytest.mark.asyncio
async def test_csv_source_extract():
    content = "sku,name,price,category\nTEST1,Laptop,999.99,laptop"
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8-sig") as f:
        f.write(content)
        temp_path = f.name
        
    try:
        source = CSVSource(temp_path)
        records = await source.extract()
        assert len(records) == 1
        assert isinstance(records[0], RawPriceRecord)
        assert records[0].sku == "TEST1"
        assert records[0].price == Decimal("999.99")
    finally:
        os.remove(temp_path)
