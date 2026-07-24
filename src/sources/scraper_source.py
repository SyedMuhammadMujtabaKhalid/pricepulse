"""
PricePulse — Scraper Source Adapter
====================================

Extracts data from rendered HTML using Playwright.

Engineering Decisions:
    1. Uses Playwright over BeautifulSoup to handle JavaScript-heavy sites (like BestBuy/Amazon).
    2. Runs headlessly by default (configurable via environment).
    3. Implements an abstract parsing method because every website's DOM is unique.
       Concrete scrapers will inherit from this and implement `parse_page()`.
"""

from abc import abstractmethod
from typing import Any
from playwright.async_api import (
    async_playwright,
    Page,
    BrowserContext,
    Error as PlaywrightError,
)
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from config.settings import get_settings
from src.core.logger import get_logger
from src.sources.base import BaseSource
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


class PlaywrightScraperSource(BaseSource):
    """
    Base class for Playwright-based web scrapers.
    Handles browser lifecycle; children handle the DOM parsing.
    """

    def __init__(self, target_url: str, source_name: str) -> None:
        super().__init__()
        self.target_url = target_url
        self._source_name = source_name

        settings = get_settings()
        self.headless = settings.scraper_headless
        self.timeout = settings.scraper_timeout_ms

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def source_type(self) -> str:
        return "scraper"

    @abstractmethod
    async def parse_page(self, page: Page) -> list[RawPriceRecord]:
        """
        Extract data from the loaded Playwright page.
        MUST be implemented by child classes (e.g., AmazonScraper).
        """
        pass

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(PlaywrightError),
        reraise=True,
    )
    async def extract(self, **kwargs: Any) -> list[RawPriceRecord]:
        """
        Orchestrate the browser lifecycle and call the parser.
        """
        log.info(
            "source.scraper.extract_started",
            source=self.source_name,
            url=self.target_url,
        )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)

                # Use a context to spoof user agent and block images/fonts for speed
                context: BrowserContext = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )

                # Block unnecessary resources to speed up scraping
                await context.route("**/*", self._route_interceptor)

                page = await context.new_page()
                page.set_default_timeout(self.timeout)

                # Navigate and wait for DOM content
                log.debug("source.scraper.navigating", url=self.target_url)
                await page.goto(self.target_url, wait_until="domcontentloaded")

                # Delegate to the child class to actually pull the data
                records = await self.parse_page(page)

                await browser.close()

                log.info(
                    "source.scraper.extract_success",
                    source=self.source_name,
                    records=len(records),
                )
                return records

        except Exception as e:
            log.error(
                "source.scraper.extract_failed", source=self.source_name, error=str(e)
            )
            raise

    async def _route_interceptor(self, route: Any) -> None:
        """Block images, fonts, and media to save bandwidth and speed up scraping."""
        if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
            await route.abort()
        else:
            await route.continue_()

    async def health_check(self) -> bool:
        """
        Scraper health check: can we launch the browser and hit the URL without a 404?
        (Kept simple; a real system might use a lightweight HTTP HEAD here instead of a full browser)
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.target_url)
                return response.status_code == 200
        except Exception as e:
            log.warning(
                "source.scraper.health_failed", source=self.source_name, error=str(e)
            )
            return False
