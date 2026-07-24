"""
PricePulse — Integration Tests for FastAPI API Layer
"""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "pricepulse-api"


def test_products_endpoint():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_alerts_endpoint():
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_changes_endpoint():
    response = client.get("/api/v1/changes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_product_history_not_found():
    response = client.get("/api/v1/products/NON_EXISTENT_SKU_12345/history")
    assert response.status_code == 404
