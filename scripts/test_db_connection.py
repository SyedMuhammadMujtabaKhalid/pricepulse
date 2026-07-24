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

    print()
    print("=" * 60)
    print("  PricePulse — Database Connection Test")
    print("=" * 60)
    print()
    print(f"  Host:     {settings.postgres_host}")
    print(f"  Port:     {settings.postgres_port}")
    print(f"  Database: {settings.postgres_db}")
    print(f"  User:     {settings.postgres_user}")
    print()

    # ── Test 1: Basic connectivity ────────────────────────────
    print("  [1/2] Testing connection...", end=" ")

    if not check_connection():
        print("❌ FAILED")
        print()
        print("  💡 Troubleshooting:")
        print("     1. Is Docker running?")
        print("        → docker-compose up -d db")
        print("     2. Is .env configured?")
        print("        → cp .env.example .env")
        print("     3. Is the port correct?")
        print(
            f"        → Check POSTGRES_PORT in .env (current: {settings.postgres_port})"
        )
        print("     4. Is PostgreSQL accepting connections?")
        print("        → docker-compose logs db")
        print()
        sys.exit(1)

    print("✅ Connected")

    # ── Test 2: Server version ────────────────────────────────
    print("  [2/2] Fetching server version...", end=" ")

    version = get_db_version()
    if version:
        # Extract just the version number (e.g., "PostgreSQL 16.3")
        short_version = version.split(",")[0] if "," in version else version
        print(f"✅ {short_version}")
    else:
        print("⚠️  Could not fetch version (non-critical)")

    # ── Summary ───────────────────────────────────────────────
    print()
    print("  " + "─" * 56)
    print(
        f"  ✅ Database is ready: {settings.postgres_db} @ "
        f"{settings.postgres_host}:{settings.postgres_port}"
    )
    print("  " + "─" * 56)
    print()


if __name__ == "__main__":
    main()
