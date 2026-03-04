import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

URL = "https://www.bazaarvoice.com/case-studies/"


class BazaarvoiceScraper(BaseScraper):
    source_name = "Bazaarvoice Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            await self._safe_goto(page, URL)
            await page.wait_for_timeout(3000)

            # Click "Show more" / "Load more" button repeatedly to load all entries
            for _ in range(30):
                btn = await page.query_selector(
                    "button:has-text('Show more'), "
                    "button:has-text('Load more'), "
                    "a:has-text('Show more'), "
                    "[class*='load-more'], [class*='show-more']"
                )
                if not btn:
                    break
                visible = await btn.is_visible()
                if not visible:
                    break
                try:
                    await btn.click()
                    await page.wait_for_timeout(1500)
                except Exception:
                    break

            # Extract case study cards
            cards = await page.query_selector_all(
                "[class*='case-study'], [class*='CaseStudy'], "
                "article, .card, [class*='card'], [class*='Card']"
            )
            if not cards:
                # Broader fallback: any link with case-study in href
                cards = await page.query_selector_all(
                    "a[href*='case-stud']"
                )

            for card in cards:
                try:
                    name = ""
                    logo = ""
                    description = ""
                    link = ""

                    # Brand name from img alt
                    img = await card.query_selector("img")
                    if img:
                        name = (
                            await img.get_attribute("alt") or ""
                        ).strip()
                        logo = (
                            await img.get_attribute("src") or ""
                        ).strip()

                    # Brand name from heading
                    if not name or name.lower() in (
                        "logo", "image", "case study", "",
                    ):
                        for sel in ("h2", "h3", "h4", "h5"):
                            el = await card.query_selector(sel)
                            if el:
                                text = (await el.inner_text()).strip()
                                if text and len(text) < 100:
                                    name = text
                                    break

                    # Link for slug fallback
                    a_tag = await card.query_selector("a")
                    if a_tag:
                        link = await a_tag.get_attribute("href") or ""
                    else:
                        tag = await card.evaluate("el => el.tagName")
                        if tag == "A":
                            link = await card.get_attribute("href") or ""

                    if not name and link:
                        slug = link.rstrip("/").split("/")[-1]
                        if slug and slug != "case-studies":
                            name = slug.replace("-", " ").title()

                    # Description
                    desc_el = await card.query_selector(
                        "p, .description, [class*='excerpt']"
                    )
                    if desc_el:
                        description = (await desc_el.inner_text()).strip()

                    # Clean name
                    name = re.sub(
                        r"\s*(case study|logo|image|customer story).*$",
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
                except Exception as e:
                    logger.warning(f"Bazaarvoice card parse error: {e}")

        except Exception as e:
            logger.error(f"Bazaarvoice scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"Bazaarvoice: Scraped {len(companies)} brands")
        return companies
