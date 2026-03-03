import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 5


class BaseScraper(ABC):
    """Base class for all accelerator scrapers."""

    source_name: str = ""

    def __init__(self, headless: bool = True, years_back: int = 1):
        self.headless = headless
        self.years_back = years_back
        self.cutoff_year = datetime.now().year - years_back

    @abstractmethod
    async def scrape(self) -> list[dict]:
        """Return list of company dicts with keys matching Company model fields."""

    async def _launch_browser(self):
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=self.headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        return pw, browser, context, page

    async def _safe_goto(self, page, url: str):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed for {url}: {e}")
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(RETRY_DELAY)
