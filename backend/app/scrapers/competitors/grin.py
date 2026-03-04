import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.grin.co/case-studies"
MAX_PAGES = 5


class GRINScraper(BaseScraper):
    source_name = "GRIN Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            for page_num in range(1, MAX_PAGES + 1):
                url = (
                    f"{BASE_URL}?page={page_num}" if page_num > 1 else BASE_URL
                )
                try:
                    await self._safe_goto(page, url)
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"GRIN page {page_num} failed: {e}")
                    break

                # Try multiple selectors for case study cards
                cards = await page.query_selector_all(
                    "figure, .case-study-card, article, "
                    "[class*='case-study'], [class*='CaseStudy']"
                )
                if not cards:
                    # Fallback: grab all linked images
                    cards = await page.query_selector_all("a[href*='case-stud']")
                if not cards:
                    logger.info(f"GRIN: No cards on page {page_num}, stopping")
                    break

                for card in cards:
                    try:
                        name = ""
                        logo = ""
                        link = ""
                        description = ""

                        # Try img alt text first
                        img = await card.query_selector("img")
                        if img:
                            name = (
                                await img.get_attribute("alt") or ""
                            ).strip()
                            logo = (
                                await img.get_attribute("src") or ""
                            ).strip()

                        # Try heading elements
                        if not name or name.lower() in (
                            "logo", "image", "case study", "",
                        ):
                            for sel in ("h2", "h3", "h4", "span", "p"):
                                el = await card.query_selector(sel)
                                if el:
                                    text = (await el.inner_text()).strip()
                                    if text and len(text) < 100:
                                        name = text
                                        break

                        # Try link href for slug-based name
                        a_tag = await card.query_selector("a")
                        if a_tag:
                            link = await a_tag.get_attribute("href") or ""
                        elif card.element_handle:
                            tag = await card.evaluate("el => el.tagName")
                            if tag == "A":
                                link = await card.get_attribute("href") or ""

                        if not name and link:
                            slug = link.rstrip("/").split("/")[-1]
                            name = slug.replace("-", " ").title()

                        # Get description if available
                        desc_el = await card.query_selector("p, .description")
                        if desc_el:
                            description = (await desc_el.inner_text()).strip()

                        # Clean name
                        name = re.sub(
                            r"\s*(case study|logo|image).*$", "", name,
                            flags=re.IGNORECASE,
                        ).strip()

                        if not name or len(name) < 2:
                            continue

                        key = name.lower()
                        if key in seen:
                            continue
                        seen.add(key)

                        website = ""
                        if link and link.startswith("http"):
                            website = link

                        companies.append({
                            "name": name,
                            "description": description[:500],
                            "website": website,
                            "founders": "",
                            "linkedin_url": "",
                            "accelerator": self.source_name,
                            "batch": "",
                            "founded_year": None,
                            "tags": "UGC Competitor Client",
                            "logo_url": logo,
                        })
                    except Exception as e:
                        logger.warning(f"GRIN card parse error: {e}")

                logger.info(
                    f"GRIN page {page_num}: {len(companies)} brands so far"
                )

        except Exception as e:
            logger.error(f"GRIN scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"GRIN: Scraped {len(companies)} brands total")
        return companies
