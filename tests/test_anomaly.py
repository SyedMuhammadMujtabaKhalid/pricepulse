from decimal import Decimal
from unittest.mock import patch
from src.quality.validators import RawPriceRecord
from src.quality.anomaly import remove_anomalies, _is_anomaly


def test_category_bounds():
    # Laptop min 100, max 5000
    valid_laptop = RawPriceRecord(
        sku="L1", name="Laptop 1", price=999.99, category="laptop"
    )
    cheap_laptop = RawPriceRecord(
        sku="L2", name="Laptop 2", price=50.0, category="laptop"
    )
    expensive_laptop = RawPriceRecord(
        sku="L3", name="Laptop 3", price=6000.0, category="laptop"
    )

    assert not _is_anomaly(valid_laptop)
    assert _is_anomaly(cheap_laptop)
    assert _is_anomaly(expensive_laptop)


def test_price_change_threshold():
    record = RawPriceRecord(sku="P1", name="Product", price=100.0)

    # Drops
    assert not _is_anomaly(record, Decimal("150.0"))  # 33% drop (valid)
    assert _is_anomaly(record, Decimal("250.0"))  # 60% drop (invalid, max 50%)

    # Increases
    assert not _is_anomaly(record, Decimal("60.0"))  # 66% increase (valid)
    assert _is_anomaly(record, Decimal("40.0"))  # 150% increase (invalid, max 100%)


@patch("src.quality.anomaly.get_session")
def test_remove_anomalies_mocked_db(mock_get_session):
    records = [
        RawPriceRecord(sku="SKU1", name="Good Laptop", price=1000.0, category="laptop"),
        RawPriceRecord(sku="SKU2", name="Bad Laptop", price=10.0, category="laptop"),
    ]
    # We won't strictly mock the whole DB response, just test the filtering logic handles it
    mock_get_session.return_value.__enter__.return_value.execute.return_value.all.return_value = (
        []
    )

    clean = remove_anomalies(records)
    assert len(clean) == 1
    assert clean[0].sku == "SKU1"
