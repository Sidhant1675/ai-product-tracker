"""
Pydantic v2 schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl

from app.models import StockStatus, AlertType


# ── Requests ──────────────────────────────────────────────

class ProductCreate(BaseModel):
    """Schema for adding a new product to track."""
    url: HttpUrl


# ── Responses ─────────────────────────────────────────────

class ProductResponse(BaseModel):
    """Full product representation for the API."""
    id: int
    url: str
    site_name: str
    product_name: str
    current_price: Optional[float] = None
    previous_price: Optional[float] = None
    currency: str = "$"
    stock_status: StockStatus = StockStatus.UNKNOWN
    stock_text: str = ""
    last_checked: Optional[datetime] = None
    created_at: Optional[datetime] = None
    is_active: bool = True
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class PriceHistoryResponse(BaseModel):
    """Price history entry."""
    id: int
    product_id: int
    price: Optional[float] = None
    stock_status: StockStatus = StockStatus.UNKNOWN
    recorded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    """Alert entry."""
    id: int
    product_id: int
    alert_type: AlertType
    message: str
    sent_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    """Aggregated stats for the dashboard."""
    total_products: int = 0
    active_monitors: int = 0
    alerts_today: int = 0
    products_in_stock: int = 0
    products_out_of_stock: int = 0
    products_low_stock: int = 0


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    detail: Optional[str] = None
