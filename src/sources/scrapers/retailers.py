"""
PricePulse — Live Retailer Web Scraper Sources
==============================================

Extracts live product price information from real e-commerce retailer websites
using Playwright browser automation.
"""

import re
from playwright.async_api import Page

from src.core.logger import get_logger
from src.sources.scraper_source import PlaywrightScraperSource
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


class NeweggScraper(PlaywrightScraperSource):
    """Scrapes live prices from Newegg product search/category listings."""

    def __init__(
        self,
        target_url: str = "https://www.newegg.com/p/pl?d=laptop",
        source_name: str = "newegg",
    ):
        super().__init__(target_url, source_name)

    async def parse_page(self, page: Page) -> list[RawPriceRecord]:
        records: list[RawPriceRecord] = []
        log.info("scraper.newegg.parsing", url=self.target_url)

        items = await page.query_selector_all(".item-cell")
        for item in items:
            try:
                title_el = await item.query_selector(".item-title")
                price_el = await item.query_selector(".price-current")
                if not title_el or not price_el:
                    continue

                title = (await title_el.inner_text()).strip()
                price_text = (await price_el.inner_text()).strip()
                price_match = re.search(r"[\d,]+\.\d{2}|[\d,]+", price_text)
                if not price_match or not title:
                    continue

                price = float(price_match.group(0).replace(",", ""))
                sku = f"NEW-{abs(hash(title)) % 1000000:06d}"

                url_attr = await title_el.get_attribute("href")

                records.append(
                    RawPriceRecord(
                        sku=sku,
                        name=title,
                        brand="NeweggHost",
                        category="Laptops",
                        url=url_attr or self.target_url,
                        price=price,
                        original_price=price,
                        in_stock=True,
                        attributes={},
                    )
                )
            except Exception as e:
                log.warning("scraper.newegg.item_failed", error=str(e))

        log.info("scraper.newegg.extracted", count=len(records))
        return records


class BHPhotoScraper(PlaywrightScraperSource):
    """Scrapes live prices from B&H Photo Video listings."""

    def __init__(
        self,
        target_url: str = "https://www.bhphotovideo.com/c/browse/Computers-Subtitles/ci/28734",
        source_name: str = "bhphoto",
    ):
        super().__init__(target_url, source_name)

    async def parse_page(self, page: Page) -> list[RawPriceRecord]:
        records: list[RawPriceRecord] = []
        log.info("scraper.bhphoto.parsing", url=self.target_url)

        items = await page.query_selector_all("[data-selenium='miniProductPage']")
        for item in items:
            try:
                title_el = await item.query_selector(
                    "[data-selenium='miniProductPageName']"
                )
                price_el = await item.query_selector("[data-selenium='pricingPrice']")
                if not title_el or not price_el:
                    continue

                title = (await title_el.inner_text()).strip()
                price_text = (await price_el.inner_text()).strip()
                price_match = re.search(r"[\d,]+\.\d{2}|[\d,]+", price_text)
                if not price_match or not title:
                    continue

                price = float(price_match.group(0).replace(",", ""))
                sku = f"BH-{abs(hash(title)) % 1000000:06d}"

                records.append(
                    RawPriceRecord(
                        sku=sku,
                        name=title,
                        brand="BHPhoto",
                        category="Computers",
                        url=self.target_url,
                        price=price,
                        original_price=price,
                        in_stock=True,
                        attributes={},
                    )
                )
            except Exception as e:
                log.warning("scraper.bhphoto.item_failed", error=str(e))

        log.info("scraper.bhphoto.extracted", count=len(records))
        return records
