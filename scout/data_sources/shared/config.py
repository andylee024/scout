"""Centralized configuration for all scrapers"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScraperConfig:
    """Global scraper configuration"""

    # ==================== Chrome/Selenium ====================
    CHROME_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    CHROME_HEADLESS = True

    # Wait times
    DEFAULT_WAIT_SECONDS = 5
    SLOW_WAIT_SECONDS = 10  # For CA DocQNet and other slow databases
    FORM_SUBMIT_WAIT = 5
    PAGE_LOAD_WAIT = 3

    # ==================== Cache Settings ====================
    SENTIMENT_CACHE_TTL_DAYS = 7  # Reviews/Reddit change frequently
    REVIEWS_CACHE_TTL_DAYS = 7

    # ==================== Output Directories ====================
    OUTPUT_DIR = "outputs"
    CACHE_DIR = "outputs/cache"

    # ==================== API Keys ====================
    GOOGLE_MAPS_API_KEY: Optional[str] = os.getenv("GOOGLE_MAPS_API_KEY")
    GOOGLE_PLACES_API_KEY: Optional[str] = os.getenv("GOOGLE_PLACES_API_KEY")
    REDDIT_CLIENT_ID: Optional[str] = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET: Optional[str] = os.getenv("REDDIT_CLIENT_SECRET")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "scout-research-bot/1.0")

    # ==================== Logging ====================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # ==================== Rate Limiting ====================
    RATE_LIMIT_DELAY_MIN = 1.0  # Minimum delay between requests (seconds)
    RATE_LIMIT_DELAY_MAX = 3.0  # Maximum delay between requests (seconds)

    # ==================== PDF Download ====================
    PDF_DOWNLOAD_TIMEOUT = 60  # Seconds
    PDF_MAX_SIZE_MB = 50  # Skip PDFs larger than this
