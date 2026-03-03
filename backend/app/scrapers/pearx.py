import logging
import re

from app.scrapers.base import BaseScraper
from app.scrapers.consumer_filter import is_consumer_company

logger = logging.getLogger(__name__)

PEARX_URL = "https://www.pear.vc/companies"


class PearXScraper(BaseScraper):
    source_name = "PearX"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        errors = []
        skipped = 0

        try:
            await self._safe_goto(page, PEARX_URL)
            await page.wait_for_timeout(3000)

            for _ in range(20):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(800)

            cards = await page.query_selector_all(
                "[class*='company'], [class*='portfolio'], .w-dyn-item"
            )
            if not cards:
                cards = await page.query_selector_all(
                    ".collection-item, .grid-item, article"
                )
            if not cards:
                cards = await page.query_selector_all("[role='listitem'], li.w-dyn-item")

            logger.info(f"PearX: Found {len(cards)} potential elements")

            seen_names = set()

            for card in cards:
                try:
                    text = await card.inner_text()
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    if not lines:
                        continue

                    name = lines[0]
                    if name in seen_names or len(name) > 150:
                        continue

                    description = ""
                    if len(lines) > 1:
                        description = " ".join(lines[1:3])

                    link_el = await card.query_selector("a[href^='http']")
                    website = ""
                    if link_el:
                        website = await link_el.get_attribute("href") or ""

                    img_el = await card.query_selector("img")
                    logo = ""
                    if img_el:
                        logo = await img_el.get_attribute("src") or ""

                    year_match = re.search(r"\b(20\d{2})\b", text)
                    founded_year = int(year_match.group(1)) if year_match else None

                    if founded_year and founded_year < self.cutoff_year:
                        continue

                    # B2C filter
                    if not is_consumer_company(text, description):
                        skipped += 1
                        continue

                    seen_names.add(name)
                    companies.append(
                        {
                            "name": name,
                            "description": description[:500],
                            "website": website,
                            "founders": "",
                            "linkedin_url": "",
                            "accelerator": "PearX",
                            "batch": "",
                            "founded_year": founded_year,
                            "tags": "Consumer",
                            "logo_url": logo,
                        }
                    )
                except Exception as e:
                    errors.append(str(e))
                    logger.warning(f"PearX card parse error: {e}")

            # Fallback: extract links
            if not companies:
                links = await page.query_selector_all("a[href]")
                for link in links:
                    try:
                        href = await link.get_attribute("href") or ""
                        text = (await link.inner_text()).strip()
                        if (
                            text
                            and len(text) < 100
                            and href.startswith("http")
                            and "pear.vc" not in href
                            and text not in seen_names
                        ):
                            # Can't filter well without description in fallback
                            seen_names.add(text)
                            companies.append(
                                {
                                    "name": text,
                                    "description": "",
                                    "website": href,
                                    "founders": "",
                                    "linkedin_url": "",
                                    "accelerator": "PearX",
                                    "batch": "",
                                    "founded_year": None,
                                    "tags": "",
                                    "logo_url": "",
                                }
                            )
                    except Exception as e:
                        errors.append(str(e))

        except Exception as e:
            errors.append(str(e))
            logger.error(f"PearX scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"PearX: Kept {len(companies)} B2C, skipped {skipped} non-consumer")
        return companies
