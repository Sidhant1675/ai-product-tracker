"""
REST API endpoints for the product tracker.
"""

from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product, PriceHistory, Alert, StockStatus, AlertType
from app.schemas import (
    ProductCreate,
    ProductResponse,
    PriceHistoryResponse,
    AlertResponse,
    DashboardStats,
    MessageResponse,
)
from app.scraper.engine import scrape_product

router = APIRouter(prefix="/api", tags=["products"])


# ── Products ──────────────────────────────────────────────


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def add_product(product_in: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Add a new product URL to track."""
    url_str = str(product_in.url)

    # Check if already tracked
    existing = await db.execute(select(Product).where(Product.url == url_str))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This URL is already being tracked.",
        )

    # Detect site name from URL
    from urllib.parse import urlparse
    parsed = urlparse(url_str)
    site_name = parsed.netloc.replace("www.", "").split(".")[0].capitalize()

    product = Product(
        url=url_str,
        site_name=site_name,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # Do an initial scrape in the background (non-blocking for response)
    # The scheduler will pick it up on the next cycle anyway
    return product


@router.get("/products", response_model=List[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_db)):
    """List all tracked products."""
    result = await db.execute(
        select(Product).order_by(Product.created_at.desc())
    )
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


@router.delete("/products/{product_id}", response_model=MessageResponse)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Stop tracking a product (deletes it and all history)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    await db.delete(product)
    return MessageResponse(message="Product removed.", detail=f"Deleted product #{product_id}")


# ── Price History ─────────────────────────────────────────


@router.get("/products/{product_id}/history", response_model=List[PriceHistoryResponse])
async def get_price_history(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get price history for a product."""
    # Verify product exists
    result = await db.execute(select(Product).where(Product.id == product_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found.")

    history = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(100)
    )
    return history.scalars().all()


# ── Manual Scrape ─────────────────────────────────────────


@router.post("/products/{product_id}/check", response_model=ProductResponse)
async def force_check_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Force an immediate scrape of a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    try:
        scraped = await scrape_product(product.url)

        old_price = product.current_price
        old_status = product.stock_status

        # Update product
        product.product_name = scraped.get("product_name", product.product_name)
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

        # Record history
        history_entry = PriceHistory(
            product_id=product.id,
            price=product.current_price,
            stock_status=product.stock_status,
        )
        db.add(history_entry)

        # Check for alerts
        from app.notifications.telegram import send_alert

        # Price drop
        if (
            old_price is not None
            and product.current_price is not None
            and product.current_price < old_price
        ):
            alert = Alert(
                product_id=product.id,
                alert_type=AlertType.PRICE_DROP,
                message=f"Price dropped from {product.currency}{old_price:.2f} to {product.currency}{product.current_price:.2f}",
            )
            db.add(alert)
            await send_alert(
                AlertType.PRICE_DROP,
                product,
                old_price,
                product.current_price,
            )

        # Back in stock
        if (
            old_status == StockStatus.OUT_OF_STOCK
            and product.stock_status == StockStatus.IN_STOCK
        ):
            alert = Alert(
                product_id=product.id,
                alert_type=AlertType.BACK_IN_STOCK,
                message=f"{product.product_name} is back in stock!",
            )
            db.add(alert)
            await send_alert(AlertType.BACK_IN_STOCK, product, None, None)

        # Low stock
        if product.stock_status == StockStatus.LOW_STOCK and old_status != StockStatus.LOW_STOCK:
            alert = Alert(
                product_id=product.id,
                alert_type=AlertType.LOW_STOCK,
                message=f"{product.product_name} is running low! {product.stock_text}",
            )
            db.add(alert)
            await send_alert(AlertType.LOW_STOCK, product, None, None)

        await db.flush()
        await db.refresh(product)

    except Exception as e:
        product.last_error = str(e)
        product.last_checked = datetime.now(timezone.utc)

    return product


# ── Stats & Alerts ────────────────────────────────────────


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    total = await db.execute(select(func.count(Product.id)))
    total_products = total.scalar() or 0

    active = await db.execute(
        select(func.count(Product.id)).where(Product.is_active == True)
    )
    active_monitors = active.scalar() or 0

    in_stock = await db.execute(
        select(func.count(Product.id)).where(Product.stock_status == StockStatus.IN_STOCK)
    )
    products_in_stock = in_stock.scalar() or 0

    out_of_stock = await db.execute(
        select(func.count(Product.id)).where(Product.stock_status == StockStatus.OUT_OF_STOCK)
    )
    products_out_of_stock = out_of_stock.scalar() or 0

    low_stock = await db.execute(
        select(func.count(Product.id)).where(Product.stock_status == StockStatus.LOW_STOCK)
    )
    products_low_stock = low_stock.scalar() or 0

    # Alerts from the last 24 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    alerts_today_q = await db.execute(
        select(func.count(Alert.id)).where(Alert.sent_at >= cutoff)
    )
    alerts_today = alerts_today_q.scalar() or 0

    return DashboardStats(
        total_products=total_products,
        active_monitors=active_monitors,
        alerts_today=alerts_today,
        products_in_stock=products_in_stock,
        products_out_of_stock=products_out_of_stock,
        products_low_stock=products_low_stock,
    )


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(db: AsyncSession = Depends(get_db)):
    """Get recent alerts (last 50)."""
    result = await db.execute(
        select(Alert).order_by(Alert.sent_at.desc()).limit(50)
    )
    return result.scalars().all()
