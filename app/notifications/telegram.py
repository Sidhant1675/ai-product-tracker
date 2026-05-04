"""
Telegram notification sender — sends alerts when product conditions change.
Gracefully degrades if Telegram credentials are not configured.
"""

import logging
from typing import Any, Optional

from app.config import get_settings
from app.models import AlertType

logger = logging.getLogger(__name__)


async def send_alert(
    alert_type: AlertType,
    product: Any,
    old_value: Optional[float],
    new_value: Optional[float],
) -> bool:
    """
    Send a Telegram alert message.

    Returns True if sent successfully, False otherwise.
    Does NOT raise exceptions — logs warnings instead.
    """
    settings = get_settings()

    if not settings.telegram_configured:
        logger.warning(
            "Telegram not configured — skipping alert. "
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
        )
        return False

    # Build the message
    message = _format_message(alert_type, product, old_value, new_value)

    try:
        from telegram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
        logger.info(f"Telegram alert sent: {alert_type.value} for {product.product_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


def _format_message(
    alert_type: AlertType,
    product: Any,
    old_value: Optional[float],
    new_value: Optional[float],
) -> str:
    """Format a human-friendly alert message with emojis."""
    name = product.product_name or "Unknown Product"
    url = product.url
    currency = product.currency or "$"

    if alert_type == AlertType.BACK_IN_STOCK:
        return (
            f"🔔 <b>Back in Stock!</b>\n\n"
            f"<b>{name}</b> is now available!\n\n"
            f"🔗 <a href=\"{url}\">View Product</a>"
        )

    elif alert_type == AlertType.PRICE_DROP:
        old = f"{currency}{old_value:.2f}" if old_value else "N/A"
        new = f"{currency}{new_value:.2f}" if new_value else "N/A"
        pct = ""
        if old_value and new_value and old_value > 0:
            pct_val = ((old_value - new_value) / old_value) * 100
            pct = f" ({pct_val:.1f}% off)"

        return (
            f"💰 <b>Price Drop!</b>\n\n"
            f"<b>{name}</b>\n"
            f"Was: <s>{old}</s>\n"
            f"Now: <b>{new}</b>{pct}\n\n"
            f"🔗 <a href=\"{url}\">View Product</a>"
        )

    elif alert_type == AlertType.LOW_STOCK:
        stock_text = product.stock_text or "Limited availability"
        return (
            f"⚠️ <b>Low Stock Alert!</b>\n\n"
            f"<b>{name}</b>\n"
            f"Status: {stock_text}\n\n"
            f"🔗 <a href=\"{url}\">View Product</a>"
        )

    elif alert_type == AlertType.PRICE_INCREASE:
        old = f"{currency}{old_value:.2f}" if old_value else "N/A"
        new = f"{currency}{new_value:.2f}" if new_value else "N/A"
        return (
            f"📈 <b>Price Increase</b>\n\n"
            f"<b>{name}</b>\n"
            f"Was: {old}\n"
            f"Now: <b>{new}</b>\n\n"
            f"🔗 <a href=\"{url}\">View Product</a>"
        )

    return f"ℹ️ Alert for {name}: {alert_type.value}\n🔗 {url}"
