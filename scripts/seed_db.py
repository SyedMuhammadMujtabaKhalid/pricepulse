"""
PricePulse — Database Seeder
=============================

Populates the database with realistic sample data for the MVP.
This gives the dashboard something to display immediately.

Run:
    python scripts/seed_db.py
"""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from src.core.logger import setup_logging, get_logger
from src.storage.database import get_session
from src.storage.models import Competitor, Product, PriceRecord, PriceChange

log = get_logger(__name__)


def generate_seed_data() -> None:
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    log.info("seed.started")

    with get_session() as session:
        # 1. Create Competitors
        competitors_data = [
            {"name": "Best Buy API", "domain": "bestbuy.com", "source_type": "api"},
            {"name": "Amazon Scraper", "domain": "amazon.com", "source_type": "scraper"},
            {"name": "Historical Dataset", "domain": "kaggle.com", "source_type": "csv"},
        ]
        
        comps = []
        for c_data in competitors_data:
            c = session.query(Competitor).filter_by(name=c_data["name"]).first()
            if not c:
                c = Competitor(**c_data)
                session.add(c)
            comps.append(c)
            
        session.flush()
        log.info("seed.competitors.created", count=len(comps))

        # 2. Create Products
        products_data = [
            {
                "sku": "LAP-DELL-XPS-13-2026",
                "name": "Dell XPS 13 OLED (2026)",
                "brand": "Dell",
                "category": "Laptops",
                "url": "https://example.com/xps13",
                "attributes": {"ram": "16GB", "storage": "512GB SSD", "cpu": "Intel Core Ultra 7"},
            },
            {
                "sku": "MON-LG-27GP850",
                "name": "LG 27GP850-B 27 inch Ultragear",
                "brand": "LG",
                "category": "Monitors",
                "url": "https://example.com/lg27",
                "attributes": {"refresh_rate": "165Hz", "resolution": "1440p", "panel": "Nano IPS"},
            },
            {
                "sku": "PER-LOGI-MX3S",
                "name": "Logitech MX Master 3S",
                "brand": "Logitech",
                "category": "Peripherals",
                "url": "https://example.com/mx3s",
                "attributes": {"connectivity": "Wireless", "sensor": "8000 DPI"},
            },
        ]
        
        prods = []
        for p_data in products_data:
            p = session.query(Product).filter_by(sku=p_data["sku"]).first()
            if not p:
                p = Product(**p_data)
                session.add(p)
            prods.append(p)
            
        session.flush()
        log.info("seed.products.created", count=len(prods))

        # 3. Create Price Records (Mock 30 days of history)
        # We will generate a slight downward trend for laptops, stable for peripherals
        base_prices = {
            "LAP-DELL-XPS-13-2026": Decimal("1299.99"),
            "MON-LG-27GP850": Decimal("399.99"),
            "PER-LOGI-MX3S": Decimal("99.99"),
        }
        
        # Check if we already have prices
        existing_prices = session.query(PriceRecord).count()
        if existing_prices > 0:
            log.info("seed.prices.skip_existing")
            return

        now = datetime.now(timezone.utc)
        run_id = "seed_run_01"
        
        for p in prods:
            base_price = base_prices[p.sku]
            
            for days_ago in range(30, -1, -1):
                record_date = now - timedelta(days=days_ago)
                
                # Introduce some variation per competitor
                for i, c in enumerate(comps):
                    # Comp 0 (Best Buy) is baseline
                    # Comp 1 (Amazon) is 5% cheaper usually
                    # Comp 2 (Historical) is stable but outdated
                    
                    price_modifier = Decimal("1.0")
                    if i == 1:
                        price_modifier = Decimal("0.95")
                        
                    # Add a price drop 5 days ago for the laptop
                    time_modifier = Decimal("1.0")
                    if p.sku == "LAP-DELL-XPS-13-2026" and days_ago <= 5:
                        time_modifier = Decimal("0.9")  # 10% drop
                        
                    current_price = base_price * price_modifier * time_modifier
                    
                    # Round to .99
                    current_price = Decimal(f"{float(current_price):.0f}") - Decimal("0.01")
                    
                    pr = PriceRecord(
                        product_id=p.id,
                        competitor_id=c.id,
                        price=current_price,
                        original_price=base_price,
                        in_stock=True,
                        scraped_at=record_date,
                        source_run_id=run_id
                    )
                    session.add(pr)

        session.commit()
        log.info("seed.prices.created", days=30)
        
        # We don't seed price_changes or alerts here, the Intelligence Engine
        # will process these raw records and generate them in Phase 6.

    log.info("seed.completed_successfully")


if __name__ == "__main__":
    generate_seed_data()
