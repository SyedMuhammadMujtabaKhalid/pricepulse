"""
PricePulse — Test Fixtures
============================

Shared pytest fixtures for all test modules.

Engineering Decisions:
    1. conftest.py is auto-discovered by pytest. Fixtures defined here
       are available to ALL test files without explicit imports.
    2. Database fixtures use a separate test database (or SQLite for
       unit tests) to avoid polluting development data.
    3. Settings fixture overrides env vars to ensure tests are
       deterministic and don't depend on local .env files.
"""

import pytest

from config.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    """
    Provide test-specific settings.

    Overrides database credentials to prevent tests from
    accidentally modifying development data.
    """
    return Settings(
        postgres_user="pricepulse_test",
        postgres_password="test_secret",
        postgres_db="pricepulse_test",
        postgres_host="localhost",
        postgres_port=5432,
        app_env="development",
        log_level="DEBUG",
        log_format="console",
    )
