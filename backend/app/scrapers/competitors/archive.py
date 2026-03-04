import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

URL = "https://www.archive.com"


class ArchiveScraper(BaseScraper):
    source_name = "Archive Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            await self._safe_goto(page, URL)
            await page.wait_for_timeout(3000)

            # Scroll to load lazy images
            for _ in range(5):
                await page.evaluate(
                    "window.scrollBy(0, window.innerHeight)"
                )
                await page.wait_for_timeout(800)

            # Extract logos — typically in marquee/logo sections
            # Alt text is often generic on this site, so rely on src filenames
            images = await page.query_selector_all("img")
            for img in images:
                try:
                    alt = (await img.get_attribute("alt") or "").strip()
                    src = (await img.get_attribute("src") or "").strip()

                    name = ""
                    logo = src

                    # Try alt text first (if meaningful)
                    if alt and alt.lower() not in (
                        "logo", "image", "photo", "icon", "brand",
                        "archive", "hero", "banner", "",
                    ) and len(alt) < 80:
                        name = alt

                    # Fallback: extract from image filename
                    if not name and src:
                        name = self._name_from_filename(src)

                    if not name:
                        continue

                    # Clean name
                    name = re.sub(
                        r"\s*(logo|icon|image|\.svg|\.png|\.jpg|\.webp).*$",
                        "", name, flags=re.IGNORECASE,
                    ).strip()
                    name = re.sub(r"[-_]+", " ", name).strip()

                    if not name or len(name) < 2 or len(name) > 80:
                        continue

                    # Skip non-brand images
                    skip_words = {
                        "archive", "hero", "banner", "background", "bg",
                        "pattern", "decoration", "arrow", "check",
                        "star", "quote", "testimonial", "screenshot",
                        "favicon", "og", "social", "share", "meta",
                    }
                    if name.lower() in skip_words:
                        continue

                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    companies.append({
                        "name": (
                            name.title() if name == name.lower() else name
                        ),
                        "description": "",
                        "website": "",
                        "founders": "",
                        "linkedin_url": "",
                        "accelerator": self.source_name,
                        "batch": "",
                        "founded_year": None,
                        "tags": "UGC Competitor Client",
                        "logo_url": logo,
                    })
                except Exception as e:
                    logger.warning(f"Archive img parse error: {e}")

        except Exception as e:
            logger.error(f"Archive scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"Archive: Scraped {len(companies)} brands")
        return companies

    @staticmethod
    def _name_from_filename(src: str) -> str:
        """Extract brand name from image URL filename."""
        filename = src.split("/")[-1].split("?")[0]
        name = re.sub(
            r"\.(svg|png|jpg|jpeg|webp|gif)$", "", filename,
            flags=re.IGNORECASE,
        )
        # Remove common suffixes
        name = re.sub(
            r"[-_]*(logo|icon|white|black|color|dark|light|small|"
            r"large|\d+x\d+|@\dx).*$",
            "", name, flags=re.IGNORECASE,
        )
        name = re.sub(r"[-_]+", " ", name).strip()
        # Skip hashes/UUIDs
        if re.match(r"^[a-f0-9]{8,}$", name, re.IGNORECASE):
            return ""
        return name
