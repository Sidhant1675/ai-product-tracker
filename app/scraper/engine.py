"""
Core scraping engine — tries lightweight httpx + BS4 first,
falls back to Playwright for JS-heavy pages.
"""

import logging
from typing import Dict, Any

import httpx

from app.config import get_settings
from app.scraper.parsers import get_parser

logger = logging.getLogger(__name__)

settings = get_settings()

# Standard headers to mimic a real browser
DEFAULT_HEADERS = {
    "User-Agent": settings.user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


async def _scrape_with_httpx(url: str) -> str | None:
    """Attempt a lightweight scrape using httpx (no JS execution)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers=DEFAULT_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

            # Check if the page has meaningful content
            if len(html) < 500:
                logger.info(f"httpx response too short for {url}, will try Playwright")
                return None

            return html

    except Exception as e:
        logger.warning(f"httpx scrape failed for {url}: {e}")
        return None


async def _scrape_with_playwright(url: str) -> str | None:
    """Fallback scrape using Playwright (headless Chromium with JS)."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=settings.user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            page = await context.new_page()

            # Stealth: remove webdriver flag
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                """
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait a bit for dynamic content
            await page.wait_for_timeout(3000)

            html = await page.content()
            await browser.close()

            return html

    except Exception as e:
        logger.error(f"Playwright scrape failed for {url}: {e}")
        return None


async def scrape_product(url: str) -> Dict[str, Any]:
    """
    Main scraping entry point.
    Tries httpx first, falls back to Playwright.
    Returns a dict with: product_name, price, currency, stock_status, stock_text
    """
    logger.info(f"Scraping: {url}")

    # Try lightweight approach first
    html = await _scrape_with_httpx(url)

    # If httpx failed or returned thin content, try Playwright
    if html is None:
        logger.info(f"Falling back to Playwright for {url}")
        html = await _scrape_with_playwright(url)

    if html is None:
        raise RuntimeError(f"All scraping methods failed for {url}")

    # Parse the HTML with the appropriate parser
    parser = get_parser(url)
    result = parser.parse(html, url)

    logger.info(f"Scraped result for {url}: {result}")
    return result
