import logging

from app.scrapers.base import BaseScraper
from app.scrapers.consumer_filter import is_consumer_company

logger = logging.getLogger(__name__)

A16Z_URL = "https://speedrun.a16z.com"


class A16ZScraper(BaseScraper):
    source_name = "a16z Speedrun"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        errors = []
        skipped = 0

        try:
            await self._safe_goto(page, A16Z_URL)
            await page.wait_for_timeout(3000)

            for _ in range(20):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(800)

            # Try multiple selector strategies
            cards = await page.query_selector_all(
                "[class*='company'], [class*='portfolio'], [class*='card']"
            )
            if not cards:
                cards = await page.query_selector_all("article, .grid > div, li")

            logger.info(f"a16z: Found {len(cards)} potential elements")

            links = await page.query_selector_all("a[href]")
            seen_names = set()

            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    text = (await link.inner_text()).strip()

                    if not text or len(text) > 200 or len(text) < 2:
                        continue
                    if text.lower() in (
                        "home", "about", "contact", "blog", "apply",
                        "sign up", "log in", "privacy", "terms",
                    ):
                        continue

                    parent = await link.evaluate_handle("el => el.parentElement")
                    parent_text = await parent.evaluate("el => el.innerText || ''")
                    parent_text = parent_text.strip()

                    if text in seen_names:
                        continue

                    if href.startswith("http") and "a16z" not in href:
                        desc_lines = [
                            l.strip()
                            for l in parent_text.split("\n")
                            if l.strip() and l.strip() != text
                        ]
                        description = desc_lines[0][:500] if desc_lines else ""

                        # B2C filter
                        if not is_consumer_company(parent_text, description):
                            skipped += 1
                            continue

                        seen_names.add(text)
                        companies.append(
                            {
                                "name": text,
                                "description": description,
                                "website": href,
                                "founders": "",
                                "linkedin_url": "",
                                "accelerator": "a16z Speedrun",
                                "batch": "",
                                "founded_year": None,
                                "tags": "Consumer",
                                "logo_url": "",
                            }
                        )
                except Exception as e:
                    errors.append(str(e))

            if not companies:
                for card in cards:
                    try:
                        text = await card.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        if not lines:
                            continue

                        name = lines[0]
                        if name in seen_names or len(name) > 100:
                            continue

                        description = lines[1] if len(lines) > 1 else ""
                        link_el = await card.query_selector("a[href]")
                        website = ""
                        if link_el:
                            website = await link_el.get_attribute("href") or ""

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
                                "accelerator": "a16z Speedrun",
                                "batch": "",
                                "founded_year": None,
                                "tags": "Consumer",
                                "logo_url": "",
                            }
                        )
                    except Exception as e:
                        errors.append(str(e))

        except Exception as e:
            errors.append(str(e))
            logger.error(f"a16z scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"a16z: Kept {len(companies)} B2C, skipped {skipped} non-consumer")
        return companies
