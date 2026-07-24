"""
PricePulse — Database Connection Test
======================================

Standalone script to verify PostgreSQL connectivity.

Run:
    python scripts/test_db_connection.py

Expected output on success:
    ✅ Connected to PostgreSQL
    📋 Server version: PostgreSQL 16.x ...
    📊 Database: pricepulse @ localhost:5432

Expected output on failure:
    ❌ Connection failed: <error details>
    💡 Troubleshooting:
       1. Is Docker running? → docker-compose up -d db
       2. Is .env configured? → cp .env.example .env
       3. Is the port correct? → Check POSTGRES_PORT in .env

This script is intentionally self-contained. It can run before any
other part of the application is set up, making it a good first
smoke test after project setup.
"""

import sys
from pathlib import Path

from config.settings import get_settings
from src.core.logger import setup_logging
from src.storage.database import check_connection, get_db_version

# Add project root to Python path (after imports)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main() -> None:
    """Run the database connection test."""
    settings = get_settings()

    # Initialize logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
    )




if __name__ == "__main__":
    main()
