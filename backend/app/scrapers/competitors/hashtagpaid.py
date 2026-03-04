import json
import logging
import re

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

URL = "https://hashtagpaid.com/case-studies"


class HashtagPaidScraper(BaseScraper):
    source_name = "#paid Client"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        seen = set()

        try:
            await self._safe_goto(page, URL)
            await page.wait_for_timeout(2000)

            # Strategy 1: Parse JSON-LD structured data
            ld_scripts = await page.query_selector_all(
                "script[type='application/ld+json']"
            )
            for script in ld_scripts:
                try:
                    raw = await script.inner_text()
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        self._extract_from_jsonld(item, companies, seen)
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"JSON-LD parse: {e}")

            # Strategy 2: HTML card parsing (fallback/supplement)
            cards = await page.query_selector_all(
                "[class*='case-study'], [class*='CaseStudy'], "
                "article, .card, [class*='card'], [class*='Card'], "
                "[class*='project'], [class*='Project']"
            )
            if not cards:
                cards = await page.query_selector_all(
                    "a[href*='case-stud']"
                )

            for card in cards:
                try:
                    name = ""
                    logo = ""
                    description = ""
                    link = ""

                    # Heading
                    for sel in ("h2", "h3", "h4", "h5"):
                        el = await card.query_selector(sel)
                        if el:
                            text = (await el.inner_text()).strip()
                            if text and len(text) < 100:
                                name = text
                                break

                    # Image
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

                    # Link
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
                        r"\s*(case study|x #paid|x hashtagpaid).*$",
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
                    logger.warning(f"#paid card parse error: {e}")

        except Exception as e:
            logger.error(f"#paid scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"#paid: Scraped {len(companies)} brands")
        return companies

    def _extract_from_jsonld(
        self, data: dict, companies: list, seen: set
    ):
        """Extract brand names from JSON-LD structured data."""
        schema_type = data.get("@type", "")

        # Handle Article, CaseStudy, WebPage types
        if schema_type in (
            "Article", "CaseStudy", "WebPage", "BlogPosting",
        ):
            name = data.get("name", "") or data.get("headline", "")
            name = re.sub(
                r"\s*(case study|x #paid|x hashtagpaid|\|.*)$",
                "", name, flags=re.IGNORECASE,
            ).strip()
            if name and len(name) >= 2:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    companies.append({
                        "name": name,
                        "description": (
                            data.get("description", "")[:500]
                        ),
                        "website": data.get("url", ""),
                        "founders": "",
                        "linkedin_url": "",
                        "accelerator": "#paid Client",
                        "batch": "",
                        "founded_year": None,
                        "tags": "UGC Competitor Client",
                        "logo_url": "",
                    })

        # Handle ItemList
        if schema_type == "ItemList":
            for item in data.get("itemListElement", []):
                if isinstance(item, dict):
                    nested = item.get("item", item)
                    if isinstance(nested, dict):
                        self._extract_from_jsonld(nested, companies, seen)
