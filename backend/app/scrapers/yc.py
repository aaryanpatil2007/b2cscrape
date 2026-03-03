import logging
import re

from app.scrapers.base import BaseScraper
from app.scrapers.consumer_filter import is_consumer_company

logger = logging.getLogger(__name__)

YC_URL = "https://www.ycombinator.com/companies"


def _parse_batch_year(batch: str) -> int | None:
    """Extract year from batch string like 'W24', 'S23'."""
    match = re.search(r"(\d{2,4})$", batch)
    if not match:
        return None
    num = int(match.group(1))
    if num < 100:
        return 2000 + num
    return num


class YCScraper(BaseScraper):
    source_name = "YC"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        errors = []
        skipped = 0

        try:
            url = f"{YC_URL}?tags=Consumer"
            await self._safe_goto(page, url)
            await page.wait_for_timeout(3000)

            # Scroll to load all companies (infinite scroll)
            prev_count = 0
            for _ in range(50):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
                cards = await page.query_selector_all("a[href^='/companies/']")
                current_count = len(cards)
                if current_count == prev_count:
                    break
                prev_count = current_count

            logger.info(f"YC: Found {prev_count} elements before B2C filter")

            cards = await page.query_selector_all("a[href^='/companies/']")
            seen_hrefs = set()

            for card in cards:
                try:
                    href = await card.get_attribute("href")
                    if not href or href in seen_hrefs or "/companies?" in href:
                        continue
                    if href in ("/companies", "/companies/"):
                        continue
                    seen_hrefs.add(href)

                    all_text = await card.inner_text()
                    lines = [l.strip() for l in all_text.split("\n") if l.strip()]

                    # Company name
                    name_el = await card.query_selector(
                        "span.text-lg, span[class*='coName'], .company-name"
                    )
                    name = await name_el.inner_text() if name_el else ""
                    if not name:
                        name = lines[0] if lines else ""
                    if not name:
                        continue

                    # Batch
                    batch = ""
                    m = re.search(
                        r"\b(SPRING|SUMMER|WINTER|FALL)\s+(20\d{2})\b",
                        all_text, re.IGNORECASE,
                    )
                    m2 = re.search(r"\b([SWF]\d{2})\b", all_text)
                    if m:
                        batch = f"{m.group(1)[0].upper()}{m.group(2)[2:]}"
                    elif m2:
                        batch = m2.group(1)

                    # Year filter
                    founded_year = _parse_batch_year(batch)
                    if founded_year and founded_year < self.cutoff_year:
                        continue

                    # Description — longest meaningful line
                    description = ""
                    desc_el = await card.query_selector(
                        "span.text-sm, span[class*='coDescription']"
                    )
                    if desc_el:
                        description = await desc_el.inner_text()
                    if not description:
                        for line in lines:
                            if line == name:
                                continue
                            if len(line) < 15 and line.isupper():
                                continue
                            if re.match(
                                r"^(SPRING|SUMMER|WINTER|FALL)\s+\d{4}$",
                                line, re.IGNORECASE,
                            ):
                                continue
                            if len(line) > len(description):
                                description = line

                    # Category tag from card
                    category_tag = ""
                    for line in lines:
                        if line == name or line == description:
                            continue
                        if 2 <= len(line) <= 25 and line.isupper():
                            category_tag = line
                            break

                    # *** FILTER: only keep consumer/B2C companies ***
                    if not is_consumer_company(all_text, description):
                        skipped += 1
                        continue

                    img_el = await card.query_selector("img")
                    logo = await img_el.get_attribute("src") if img_el else ""

                    companies.append(
                        {
                            "name": name.strip(),
                            "description": description.strip(),
                            "website": f"https://www.ycombinator.com{href}",
                            "founders": "",
                            "linkedin_url": "",
                            "accelerator": "YC",
                            "batch": batch.strip(),
                            "founded_year": founded_year,
                            "tags": category_tag or "Consumer",
                            "logo_url": logo or "",
                        }
                    )
                except Exception as e:
                    errors.append(str(e))
                    logger.warning(f"YC card parse error: {e}")

        except Exception as e:
            errors.append(str(e))
            logger.error(f"YC scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(
            f"YC: Kept {len(companies)} B2C companies, skipped {skipped} non-consumer"
        )
        return companies
