from decimal import Decimal
from unittest.mock import patch, MagicMock
from src.engine.price_detector import PriceChangeDetector
from src.storage.models import PriceRecord


@patch("src.engine.price_detector.get_session")
def test_price_detector_no_new_records(mock_session):
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.all.return_value = []
    mock_session.return_value.__enter__.return_value = mock_db

    detector = PriceChangeDetector()
    assert detector.run("run_123") == 0


@patch("src.engine.price_detector.get_session")
def test_price_detector_with_change(mock_session):
    mock_db = MagicMock()

    new_record = MagicMock(spec=PriceRecord)
    new_record.product_id = "prod_1"
    new_record.competitor_id = "comp_1"
    new_record.price = Decimal("90.0")

    prev_record = MagicMock(spec=PriceRecord)
    prev_record.price = Decimal("100.0")

    mock_db.query.return_value.filter_by.return_value.all.return_value = [new_record]
    mock_db.execute.return_value.scalar_one_or_none.return_value = prev_record

    mock_session.return_value.__enter__.return_value = mock_db

    detector = PriceChangeDetector()
    changes = detector.run("run_123")
    assert changes == 1
    mock_db.add.assert_called()
