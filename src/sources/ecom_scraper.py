"""
PricePulse — Playwright E-Commerce Scraper Source
===================================================

Extracts real-time price and product records from e-commerce product pages using Playwright.
"""

import re
from playwright.async_api import Page

from src.core.logger import get_logger
from src.sources.scraper_source import PlaywrightScraperSource
from src.quality.validators import RawPriceRecord

log = get_logger(__name__)


class ECommercePlaywrightScraper(PlaywrightScraperSource):
    """
    Configurable Playwright Scraper that extracts product information
    from live e-commerce product detail or category pages using CSS selectors.
    """

    def __init__(
        self, target_url: str, source_name: str, selectors: dict[str, str] | None = None
    ) -> None:
        super().__init__(target_url, source_name)
        self.selectors = selectors or {
            "container": ".product-item, .product-card, article.product_pod, div.product-detail",
            "name": "h1, .product-title, .title, h3 a",
            "sku": "[data-sku], .sku-value, .product-sku",
            "price": ".price, .product-price, .current-price, p.price_color",
            "original_price": ".original-price, .old-price, .was-price",
            "in_stock": ".in-stock, .stock-status, p.instock",
        }

    async def parse_page(self, page: Page) -> list[RawPriceRecord]:
        """
        Parses elements from page matching CSS selectors.
        """
        records: list[RawPriceRecord] = []
        log.info("scraper.ecom.parsing", url=self.target_url)

        # Check container elements
        containers = await page.query_selector_all(self.selectors["container"])

        if not containers:
            # Single product page fallback
            records.extend(await self._parse_single_product_page(page))
        else:
            for item in containers:
                try:
                    name_el = await item.query_selector(self.selectors["name"])
                    price_el = await item.query_selector(self.selectors["price"])

                    if not name_el or not price_el:
                        continue

                    name_text = (await name_el.inner_text()).strip()
                    price_text = (await price_el.inner_text()).strip()

                    # Clean price string (e.g. "$1,299.99" -> 1299.99)
                    price_clean = self._clean_price(price_text)
                    if price_clean is None:
                        continue

                    # SKU generation/extraction
                    sku_el = (
                        await item.query_selector(self.selectors["sku"])
                        if "sku" in self.selectors
                        else None
                    )
                    sku_text = (
                        (await sku_el.inner_text()).strip()
                        if sku_el
                        else f"SKU-{abs(hash(name_text)) % 1000000:06d}"
                    )

                    # URL
                    url_el = await item.query_selector("a")
                    item_url = (
                        (await url_el.get_attribute("href"))
                        if url_el
                        else self.target_url
                    )
                    if item_url and not item_url.startswith("http"):
                        from urllib.parse import urljoin

                        item_url = urljoin(self.target_url, item_url)

                    records.append(
                        RawPriceRecord(
                            sku=sku_text,
                            name=name_text,
                            brand="EComStore",
                            category="Electronics",
                            url=item_url or self.target_url,
                            price=price_clean,
                            original_price=price_clean,
                            in_stock=True,
                            attributes={},
                        )
                    )
                except Exception as e:
                    log.warning("scraper.ecom.item_parse_failed", error=str(e))

        log.info("scraper.ecom.parsed_records", count=len(records))
        return records

    async def _parse_single_product_page(self, page: Page) -> list[RawPriceRecord]:
        """Fallback for single product detail page."""
        try:
            title_el = await page.query_selector("h1")
            price_el = await page.query_selector(self.selectors["price"])

            if title_el and price_el:
                title = (await title_el.inner_text()).strip()
                price = self._clean_price(await price_el.inner_text())
                if title and price is not None:
                    sku = f"SKU-{abs(hash(title)) % 1000000:06d}"
                    return [
                        RawPriceRecord(
                            sku=sku,
                            name=title,
                            brand="EComStore",
                            category="Electronics",
                            url=self.target_url,
                            price=price,
                            original_price=price,
                            in_stock=True,
                            attributes={},
                        )
                    ]
        except Exception as e:
            log.warning("scraper.ecom.single_page_failed", error=str(e))
        return []

    def _clean_price(self, price_str: str) -> float | None:
        if not price_str:
            return None
        match = re.search(r"[\d,]+\.\d{2}|[\d,]+", price_str)
        if match:
            clean = match.group(0).replace(",", "")
            try:
                return float(clean)
            except ValueError:
                return None
        return None
