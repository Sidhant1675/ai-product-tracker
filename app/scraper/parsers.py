"""
Site-specific parsers for extracting product data from HTML.
Each parser extracts: product_name, price, currency, stock_status, stock_text
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from app.models import StockStatus

logger = logging.getLogger(__name__)


# ── Low-stock keyword patterns ────────────────────────────

LOW_STOCK_PATTERNS = [
    r"only \d+ left",
    r"just \d+ left",
    r"limited stock",
    r"low stock",
    r"few left",
    r"almost gone",
    r"selling fast",
    r"hurry",
    r"last chance",
    r"\d+ remaining",
    r"limited availability",
    r"while supplies last",
]

OUT_OF_STOCK_PATTERNS = [
    r"out of stock",
    r"currently unavailable",
    r"sold out",
    r"not available",
    r"unavailable",
    r"no longer available",
    r"coming soon",
    r"notify me",
    r"pre-order",
]

IN_STOCK_PATTERNS = [
    r"in stock",
    r"add to cart",
    r"add to bag",
    r"buy now",
    r"available",
    r"ships? (from|in)",
]


def _extract_price(text: str) -> Optional[float]:
    """Extract a numeric price from text like '$49.99' or '£129.00'."""
    if not text:
        return None
    # Remove commas, spaces
    cleaned = text.strip().replace(",", "").replace(" ", "")
    # Match price patterns
    match = re.search(r"[\d]+\.?\d*", cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _extract_currency(text: str) -> str:
    """Extract currency symbol from price text."""
    if not text:
        return "$"
    text = text.strip()
    for symbol in ["$", "€", "£", "¥", "₹", "₩", "kr", "zł"]:
        if symbol in text:
            return symbol
    return "$"


def _detect_stock_status(page_text: str) -> tuple[StockStatus, str]:
    """Detect stock status from page text using keyword patterns."""
    text_lower = page_text.lower()

    # Check out-of-stock first (more specific)
    for pattern in OUT_OF_STOCK_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return StockStatus.OUT_OF_STOCK, match.group()

    # Check low stock
    for pattern in LOW_STOCK_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return StockStatus.LOW_STOCK, match.group()

    # Check in-stock
    for pattern in IN_STOCK_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            return StockStatus.IN_STOCK, match.group()

    return StockStatus.UNKNOWN, ""


class AmazonParser:
    """Parser for Amazon product pages."""

    @staticmethod
    def can_parse(url: str) -> bool:
        return "amazon." in url.lower()

    @staticmethod
    def parse(html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        result: Dict[str, Any] = {}

        # Product name
        title_el = soup.select_one("#productTitle")
        if title_el:
            result["product_name"] = title_el.get_text(strip=True)

        # Price — try multiple selectors
        price_text = None
        for selector in [
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price-whole",
            'span[data-a-color="price"] .a-offscreen',
        ]:
            el = soup.select_one(selector)
            if el:
                price_text = el.get_text(strip=True)
                break

        if price_text:
            result["price"] = _extract_price(price_text)
            result["currency"] = _extract_currency(price_text)

        # Stock status
        avail_el = soup.select_one("#availability")
        if avail_el:
            avail_text = avail_el.get_text(strip=True)
            status, stock_text = _detect_stock_status(avail_text)
            result["stock_status"] = status
            result["stock_text"] = stock_text or avail_text
        else:
            # Fallback: check full page
            status, stock_text = _detect_stock_status(soup.get_text())
            result["stock_status"] = status
            result["stock_text"] = stock_text

        return result


class NikeParser:
    """Parser for Nike product pages."""

    @staticmethod
    def can_parse(url: str) -> bool:
        return "nike.com" in url.lower()

    @staticmethod
    def parse(html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        result: Dict[str, Any] = {}

        # Product name
        for selector in [
            'h1[data-test="product-title"]',
            "#pdp_product_title",
            "h1.headline-2",
            "h1",
        ]:
            el = soup.select_one(selector)
            if el:
                result["product_name"] = el.get_text(strip=True)
                break

        # Price
        for selector in [
            '[data-test="product-price"]',
            ".product-price",
            'div[data-test="product-price-reduced"]',
        ]:
            el = soup.select_one(selector)
            if el:
                price_text = el.get_text(strip=True)
                result["price"] = _extract_price(price_text)
                result["currency"] = _extract_currency(price_text)
                break

        # Stock — Nike usually shows "Sold Out" or "Coming Soon"
        page_text = soup.get_text()
        status, stock_text = _detect_stock_status(page_text)
        result["stock_status"] = status
        result["stock_text"] = stock_text

        return result


class GenericParser:
    """Generic parser using heuristics, JSON-LD, and Open Graph meta tags."""

    @staticmethod
    def can_parse(url: str) -> bool:
        return True  # Fallback parser

    @staticmethod
    def parse(html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        result: Dict[str, Any] = {}

        # 1. Try JSON-LD structured data
        json_ld_data = GenericParser._parse_json_ld(soup)
        if json_ld_data:
            result.update(json_ld_data)

        # 2. Try Open Graph meta tags
        if "product_name" not in result:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                result["product_name"] = og_title["content"]

        if "price" not in result:
            og_price = soup.find("meta", property="product:price:amount")
            if og_price and og_price.get("content"):
                result["price"] = _extract_price(og_price["content"])
            og_currency = soup.find("meta", property="product:price:currency")
            if og_currency and og_currency.get("content"):
                result["currency"] = og_currency["content"]

        # 3. Fallback: page title
        if "product_name" not in result:
            title_el = soup.find("title")
            if title_el:
                result["product_name"] = title_el.get_text(strip=True)

        # 4. Fallback: find prices in the page
        if "price" not in result:
            # Look for common price patterns in the page
            price_pattern = re.compile(r'[\$€£¥₹]\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?')
            page_text = soup.get_text()
            price_match = price_pattern.search(page_text)
            if price_match:
                price_text = price_match.group()
                result["price"] = _extract_price(price_text)
                result["currency"] = _extract_currency(price_text)

        # 5. Stock status from page text
        if "stock_status" not in result:
            page_text = soup.get_text()
            status, stock_text = _detect_stock_status(page_text)
            result["stock_status"] = status
            result["stock_text"] = stock_text

        return result

    @staticmethod
    def _parse_json_ld(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract product data from JSON-LD structured data."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string or "")
                # Handle both single objects and arrays
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product" or (
                        isinstance(item.get("@type"), list) and "Product" in item["@type"]
                    ):
                        result: Dict[str, Any] = {}
                        if "name" in item:
                            result["product_name"] = item["name"]

                        offers = item.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}

                        if "price" in offers:
                            result["price"] = float(offers["price"])
                        if "priceCurrency" in offers:
                            result["currency"] = offers["priceCurrency"]

                        availability = offers.get("availability", "").lower()
                        if "instock" in availability:
                            result["stock_status"] = StockStatus.IN_STOCK
                            result["stock_text"] = "In Stock"
                        elif "outofstock" in availability:
                            result["stock_status"] = StockStatus.OUT_OF_STOCK
                            result["stock_text"] = "Out of Stock"
                        elif "limitedavailability" in availability:
                            result["stock_status"] = StockStatus.LOW_STOCK
                            result["stock_text"] = "Limited Availability"

                        return result
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        return None


# Parser registry — order matters (specific → generic)
PARSERS = [AmazonParser, NikeParser, GenericParser]


def get_parser(url: str):
    """Get the appropriate parser for a URL."""
    for parser in PARSERS:
        if parser.can_parse(url):
            return parser
    return GenericParser
