"""
APScheduler job definitions — periodic scraping of all tracked products.
"""

import asyncio
import random
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models import Product, PriceHistory, Alert, StockStatus, AlertType
from app.scraper.engine import scrape_product
from app.notifications.telegram import send_alert

logger = logging.getLogger(__name__)


async def check_all_products():
    """
    Periodic job: scrape every active product, detect changes, send alerts.
    Called by APScheduler on the configured interval.
    """
    logger.info("=== Starting scheduled product check ===")

    async with async_session() as db:
        result = await db.execute(
            select(Product).where(Product.is_active == True)
        )
        products = result.scalars().all()

        if not products:
            logger.info("No active products to check.")
            return

        logger.info(f"Checking {len(products)} active product(s)...")

        for product in products:
            # Random jitter to avoid burst traffic (0-30 seconds)
            jitter = random.uniform(0, 30)
            await asyncio.sleep(jitter)

            try:
                scraped = await scrape_product(product.url)

                old_price = product.current_price
                old_status = product.stock_status

                # Update product fields
                if scraped.get("product_name") and scraped["product_name"] != "Unknown Product":
                    product.product_name = scraped["product_name"]

                if scraped.get("price") is not None:
                    product.previous_price = product.current_price
                    product.current_price = scraped["price"]

                if scraped.get("currency"):
                    product.currency = scraped["currency"]

                if scraped.get("stock_status"):
                    product.stock_status = scraped["stock_status"]

                if scraped.get("stock_text"):
                    product.stock_text = scraped["stock_text"]

                product.last_checked = datetime.now(timezone.utc)
                product.last_error = None

                # Record price history
                history_entry = PriceHistory(
                    product_id=product.id,
                    price=product.current_price,
                    stock_status=product.stock_status,
                )
                db.add(history_entry)

                # --- Detect changes and send alerts ---

                # Price drop
                if (
                    old_price is not None
                    and product.current_price is not None
                    and product.current_price < old_price
                ):
                    pct = ((old_price - product.current_price) / old_price) * 100
                    msg = (
                        f"Price dropped from {product.currency}{old_price:.2f} "
                        f"to {product.currency}{product.current_price:.2f} "
                        f"({pct:.1f}% off)"
                    )
                    alert = Alert(
                        product_id=product.id,
                        alert_type=AlertType.PRICE_DROP,
                        message=msg,
                    )
                    db.add(alert)
                    await send_alert(AlertType.PRICE_DROP, product, old_price, product.current_price)
                    logger.info(f"ALERT: Price drop for {product.product_name}")

                # Back in stock
                if (
                    old_status == StockStatus.OUT_OF_STOCK
                    and product.stock_status == StockStatus.IN_STOCK
                ):
                    msg = f"{product.product_name} is back in stock!"
                    alert = Alert(
                        product_id=product.id,
                        alert_type=AlertType.BACK_IN_STOCK,
                        message=msg,
                    )
                    db.add(alert)
                    await send_alert(AlertType.BACK_IN_STOCK, product, None, None)
                    logger.info(f"ALERT: Back in stock — {product.product_name}")

                # Low stock (only when transitioning to low stock)
                if (
                    product.stock_status == StockStatus.LOW_STOCK
                    and old_status != StockStatus.LOW_STOCK
                ):
                    msg = f"{product.product_name} is running low! {product.stock_text}"
                    alert = Alert(
                        product_id=product.id,
                        alert_type=AlertType.LOW_STOCK,
                        message=msg,
                    )
                    db.add(alert)
                    await send_alert(AlertType.LOW_STOCK, product, None, None)
                    logger.info(f"ALERT: Low stock — {product.product_name}")

            except Exception as e:
                product.last_error = str(e)
                product.last_checked = datetime.now(timezone.utc)
                logger.error(f"Error checking {product.url}: {e}")

        await db.commit()
        logger.info("=== Scheduled product check complete ===")
