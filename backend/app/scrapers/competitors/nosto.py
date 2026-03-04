import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

URL = "https://www.nosto.com/customers/"


class NostoScraper(BaseScraper):
    source_name = "Nosto Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            await self._safe_goto(page, URL)
            await page.wait_for_timeout(3000)

            # Scroll to trigger lazy-loading of carousels/logos
            for _ in range(5):
                await page.evaluate(
                    "window.scrollBy(0, window.innerHeight)"
                )
                await page.wait_for_timeout(1000)

            # Click any carousel arrows to reveal more logos
            for _ in range(10):
                arrow = await page.query_selector(
                    "[class*='next'], [class*='arrow-right'], "
                    "button[aria-label*='next'], "
                    "[class*='carousel'] button:last-child, "
                    "[class*='slider'] button:last-child"
                )
                if arrow:
                    try:
                        await arrow.click()
                        await page.wait_for_timeout(800)
                    except Exception:
                        break
                else:
                    break

            # Extract all images on the page (logos + case study images)
            images = await page.query_selector_all("img")
            for img in images:
                try:
                    alt = (await img.get_attribute("alt") or "").strip()
                    src = (await img.get_attribute("src") or "").strip()

                    name = ""
                    logo = src

                    # Prefer alt text
                    if alt and alt.lower() not in (
                        "logo", "image", "photo", "nosto", "icon",
                        "arrow", "close", "menu", "hero", "",
                    ):
                        name = alt

                    # Fallback: extract from SVG/image filename
                    if not name and src:
                        name = self._name_from_src(src)

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

                    # Skip obvious non-brand images
                    skip_words = {
                        "nosto", "hero", "banner", "background", "bg",
                        "pattern", "decoration", "arrow", "check",
                        "star", "quote", "testimonial", "screenshot",
                    }
                    if name.lower() in skip_words:
                        continue

                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    companies.append({
                        "name": name.title() if name == name.lower() else name,
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
                    logger.warning(f"Nosto img parse error: {e}")

            # Also look for customer/case study cards with names
            cards = await page.query_selector_all(
                "[class*='customer'], [class*='Customer'], "
                "[class*='case-study'], article, "
                "[class*='card'], [class*='Card']"
            )
            for card in cards:
                try:
                    name = ""
                    for sel in ("h2", "h3", "h4", "h5"):
                        el = await card.query_selector(sel)
                        if el:
                            text = (await el.inner_text()).strip()
                            if text and len(text) < 80:
                                name = text
                                break

                    if not name:
                        continue

                    name = re.sub(
                        r"\s*(case study|customer story|success story).*$",
                        "", name, flags=re.IGNORECASE,
                    ).strip()

                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)

                    link_el = await card.query_selector("a")
                    link = ""
                    if link_el:
                        link = await link_el.get_attribute("href") or ""

                    companies.append({
                        "name": name,
                        "description": "",
                        "website": link if link.startswith("http") else "",
                        "founders": "",
                        "linkedin_url": "",
                        "accelerator": self.source_name,
                        "batch": "",
                        "founded_year": None,
                        "tags": "UGC Competitor Client",
                        "logo_url": "",
                    })
                except Exception as e:
                    logger.warning(f"Nosto card parse error: {e}")

        except Exception as e:
            logger.error(f"Nosto scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"Nosto: Scraped {len(companies)} brands")
        return companies

    @staticmethod
    def _name_from_src(src: str) -> str:
        """Extract brand name from image URL filename."""
        # Get filename without extension
        filename = src.split("/")[-1].split("?")[0]
        name = re.sub(r"\.(svg|png|jpg|jpeg|webp|gif)$", "", filename, flags=re.IGNORECASE)
        # Remove common non-brand suffixes
        name = re.sub(
            r"[-_]*(logo|icon|white|black|color|dark|light|small|large|\d+x\d+).*$",
            "", name, flags=re.IGNORECASE,
        )
        name = re.sub(r"[-_]+", " ", name).strip()
        # Skip hashes/UUIDs
        if re.match(r"^[a-f0-9]{8,}$", name, re.IGNORECASE):
            return ""
        return name
