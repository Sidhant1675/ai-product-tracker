"""
SQLAlchemy ORM models for the product tracker.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class StockStatus(str, enum.Enum):
    """Product stock status."""
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"
    UNKNOWN = "unknown"


class AlertType(str, enum.Enum):
    """Types of alerts we can send."""
    PRICE_DROP = "price_drop"
    BACK_IN_STOCK = "back_in_stock"
    LOW_STOCK = "low_stock"
    PRICE_INCREASE = "price_increase"


class Product(Base):
    """A tracked product."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, unique=True)
    site_name = Column(String(255), default="Unknown")
    product_name = Column(String(1024), default="Unknown Product")
    current_price = Column(Float, nullable=True)
    previous_price = Column(Float, nullable=True)
    currency = Column(String(10), default="$")
    stock_status = Column(
        Enum(StockStatus), default=StockStatus.UNKNOWN
    )
    stock_text = Column(String(512), default="")
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    is_active = Column(Boolean, default=True)
    last_error = Column(Text, nullable=True)

    # Relationships
    price_history = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    alerts = relationship(
        "Alert", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Product {self.id}: {self.product_name}>"


class PriceHistory(Base):
    """Historical price/stock records for a product."""

    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    price = Column(Float, nullable=True)
    stock_status = Column(Enum(StockStatus), default=StockStatus.UNKNOWN)
    recorded_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    product = relationship("Product", back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory product={self.product_id} price={self.price}>"


class Alert(Base):
    """A notification alert that was sent."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    alert_type = Column(Enum(AlertType), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    product = relationship("Product", back_populates="alerts")

    def __repr__(self):
        return f"<Alert {self.alert_type} for product={self.product_id}>"
