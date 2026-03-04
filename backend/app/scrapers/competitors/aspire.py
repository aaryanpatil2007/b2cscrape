import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.aspire.io/stories"
MAX_PAGES = 10


class AspireScraper(BaseScraper):
    source_name = "Aspire Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            await self._safe_goto(page, BASE_URL)
            await page.wait_for_timeout(3000)

            for page_num in range(1, MAX_PAGES + 1):
                if page_num > 1:
                    # Try pagination: click next page or page number
                    navigated = False
                    for sel in (
                        f"a[href*='page={page_num}']",
                        f"a[href*='page/{page_num}']",
                        "a:has-text('Next')",
                        "button:has-text('Next')",
                        f"a:has-text('{page_num}')",
                        "[class*='next']",
                        "[class*='pagination'] a:last-child",
                    ):
                        btn = await page.query_selector(sel)
                        if btn:
                            visible = await btn.is_visible()
                            if visible:
                                try:
                                    await btn.click()
                                    await page.wait_for_timeout(2500)
                                    navigated = True
                                    break
                                except Exception:
                                    continue
                    if not navigated:
                        # Try direct URL navigation
                        try:
                            url = f"{BASE_URL}?page={page_num}"
                            await self._safe_goto(page, url)
                            await page.wait_for_timeout(2000)
                        except Exception:
                            logger.info(
                                f"Aspire: No more pages at {page_num}"
                            )
                            break

                # Extract story/case study cards
                cards = await page.query_selector_all(
                    "[class*='story'], [class*='Story'], "
                    "article, .card, [class*='card'], [class*='Card'], "
                    "[class*='case-study'], [class*='CaseStudy']"
                )
                if not cards:
                    cards = await page.query_selector_all(
                        "a[href*='/stories/'], a[href*='/story/']"
                    )
                if not cards:
                    logger.info(
                        f"Aspire: No cards on page {page_num}, stopping"
                    )
                    break

                page_brands = 0
                for card in cards:
                    try:
                        name = ""
                        logo = ""
                        description = ""
                        link = ""

                        # Brand name from headings
                        for sel in ("h3", "h4", "h2", "h5"):
                            el = await card.query_selector(sel)
                            if el:
                                text = (await el.inner_text()).strip()
                                if text and len(text) < 100:
                                    name = text
                                    break

                        # Brand name from img alt
                        img = await card.query_selector("img")
                        if img:
                            alt = (
                                await img.get_attribute("alt") or ""
                            ).strip()
                            if alt and not name:
                                name = alt
                            logo = (
                                await img.get_attribute("src") or ""
                            ).strip()

                        # Link for slug fallback
                        a_tag = await card.query_selector("a")
                        if a_tag:
                            link = await a_tag.get_attribute("href") or ""
                        else:
                            tag = await card.evaluate("el => el.tagName")
                            if tag == "A":
                                link = (
                                    await card.get_attribute("href") or ""
                                )

                        if not name and link:
                            slug = link.rstrip("/").split("/")[-1]
                            if slug and slug not in ("stories", "story"):
                                name = slug.replace("-", " ").title()

                        # Description
                        desc_el = await card.query_selector(
                            "p, .description, [class*='excerpt']"
                        )
                        if desc_el:
                            description = (
                                await desc_el.inner_text()
                            ).strip()

                        # Clean name — remove common suffixes
                        name = re.sub(
                            r"\s*(case study|story|success story).*$",
                            "", name, flags=re.IGNORECASE,
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
                        page_brands += 1
                    except Exception as e:
                        logger.warning(f"Aspire card parse error: {e}")

                logger.info(
                    f"Aspire page {page_num}: +{page_brands} brands "
                    f"({len(companies)} total)"
                )

        except Exception as e:
            logger.error(f"Aspire scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"Aspire: Scraped {len(companies)} brands total")
        return companies
