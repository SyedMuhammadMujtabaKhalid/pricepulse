import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from src.pipeline.runner import PricePulsePipeline
from src.quality.validators import RawPriceRecord
from src.sources.base import BaseSource

class MockSource(BaseSource):
    def __init__(self, name="mock_source", type="api"):
        super().__init__()
        self._name = name
        self._type = type
        
    @property
    def source_name(self): return self._name
    
    @property
    def source_type(self): return self._type
    
    async def health_check(self): return True
    
    async def extract(self):
        return [RawPriceRecord(sku="P1", name="Product 1", price=Decimal("100.0"))]

@pytest.mark.asyncio
@patch("src.pipeline.runner.get_session")
async def test_pipeline_run(mock_session):
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    class MockComp:
        name = "mock_source"
        id = 1
    class MockProd:
        sku = "P1"
        id = 1
    mock_db.query.return_value.filter.return_value.all.side_effect = [
        [MockComp()], # db_comps
        [MockProd()] # db_prods
    ]
    
    sources = [MockSource()]
    pipeline = PricePulsePipeline(sources)
    result = await pipeline.run()
    
    assert result.extracted == 1
    assert result.validated == 1
    mock_db.execute.assert_called()
