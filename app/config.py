"""
Application configuration loaded from environment variables / .env file.
Uses pydantic-settings for type-safe config with validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings — loaded from .env file or environment variables."""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scraping
    scrape_interval_seconds: int = 180
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./tracker.db"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def telegram_configured(self) -> bool:
        """Check if Telegram credentials are set."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
