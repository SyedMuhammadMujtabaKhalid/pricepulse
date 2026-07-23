"""
PricePulse — Pipeline Entry Point
===================================

Initializes the database schema and runs the ETL pipeline.

Usage:
    python scripts/run_pipeline.py
    docker compose up pipeline
"""

import asyncio
import os
import sys

# Ensure project root is on PYTHONPATH when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.logger import get_logger
from src.storage.database import get_engine, Base
# Import models so Base.metadata knows about all tables
import src.storage.models  # noqa: F401
from src.pipeline.runner import PricePulsePipeline
from src.sources.csv_source import CSVSource
from src.sources.api_source import APISource

from src.notifications.notifiers import ConsoleNotifier, TelegramNotifier, DiscordWebhookNotifier, SMTPNotifier
from src.sources.ecom_scraper import ECommercePlaywrightScraper

log = get_logger(__name__)


def init_database():
    """
    Create all tables from SQLAlchemy metadata if they don't exist.

    This is idempotent: create_all() uses IF NOT EXISTS under the hood,
    so it safely skips tables that are already present.
    """
    engine = get_engine()
    log.info("database.init.creating_tables")
    Base.metadata.create_all(bind=engine)
    log.info("database.init.tables_ready")


def build_notifiers():
    """Build list of active notifiers based on environment variables."""
    notifiers = [ConsoleNotifier()]

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat:
        notifiers.append(TelegramNotifier(telegram_token, telegram_chat))
        log.info("notifier.registered", type="telegram")

    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_webhook:
        notifiers.append(DiscordWebhookNotifier(discord_webhook))
        log.info("notifier.registered", type="discord")

    return notifiers


async def main():
    # Step 1: Ensure database schema exists
    init_database()

    # Step 2: Configure sources
    csv_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "laptops.csv")

    sources = [
        CSVSource(csv_path),
        APISource("https://dummyjson.com/products/category/laptops", "dummy_api"),
    ]

    # Optional live web scraper source if target URL provided
    scraper_url = os.getenv("SCRAPER_TARGET_URL")
    if scraper_url:
        sources.append(ECommercePlaywrightScraper(scraper_url, "live_playwright_scraper"))
        log.info("source.registered", type="playwright_scraper", url=scraper_url)

    notifiers = build_notifiers()

    # Step 3: Run pipeline
    log.info("pipeline.entry.starting", sources=len(sources), notifiers=len(notifiers))
    pipeline = PricePulsePipeline(sources, notifiers=notifiers)
    result = await pipeline.run()
    log.info(
        "pipeline.entry.finished",
        extracted=result.extracted,
        validated=result.validated,
        stored=result.stored,
        errors=result.errors,
    )


if __name__ == "__main__":
    asyncio.run(main())
