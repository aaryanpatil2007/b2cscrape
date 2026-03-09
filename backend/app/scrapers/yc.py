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

    async def _scrape_company_detail(self, context, href: str) -> dict:
        """Open a company detail page to extract website and founder names."""
        detail = {"website": "", "founders": "", "linkedin_url": ""}
        page = await context.new_page()
        try:
            url = f"https://www.ycombinator.com{href}"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1500)

            # Domains to skip when looking for the company website
            SKIP_DOMAINS = [
                "ycombinator.com",
                "startupschool.org",
                "bookface.ycombinator.com",
                "news.ycombinator.com",
                "account.ycombinator.com",
                "linkedin.com",
                "twitter.com",
                "x.com",
                "facebook.com",
                "crunchbase.com",
                "github.com",
            ]

            # Strategy 1: Look for link whose visible text IS the domain
            # (e.g. "resonate.audio" displayed as link text)
            links = await page.query_selector_all("a[href^='http']")
            for link in links:
                link_href = await link.get_attribute("href") or ""
                try:
                    link_text = (await link.inner_text()).strip().lower()
                except Exception:
                    continue

                # Collect LinkedIn URL
                if "linkedin.com" in link_href and not detail["linkedin_url"]:
                    detail["linkedin_url"] = link_href

                if any(d in link_href for d in SKIP_DOMAINS):
                    continue

                # If link text looks like a domain (e.g. "resonate.audio")
                if re.match(r"^[a-z0-9][\w.-]+\.[a-z]{2,}$", link_text):
                    detail["website"] = link_href
                    break

            # Strategy 2: If not found, look for links in the main content area
            # (skip the first ~28 nav links)
            if not detail["website"]:
                all_links = await page.query_selector_all("a[href^='http']")
                for link in all_links[25:]:  # Skip header/nav links
                    link_href = await link.get_attribute("href") or ""
                    if any(d in link_href for d in SKIP_DOMAINS):
                        continue
                    detail["website"] = link_href
                    break

            # Founder names — look for "Active Founders" or "Founders" section
            page_text = await page.inner_text("body")
            founder_names = []

            founders_match = re.search(
                r"(?:Active\s+)?Founders?\s*\n((?:[^\n]+\n){1,10})",
                page_text,
                re.IGNORECASE,
            )
            if founders_match:
                block = founders_match.group(1)
                for line in block.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Founder names are typically short (2-4 words, capitalized)
                    if (
                        re.match(r"^[A-Z][a-z]+ [A-Z]", line)
                        and len(line.split()) <= 5
                        and len(line) < 50
                    ):
                        founder_names.append(line)
                    else:
                        if founder_names:
                            break

            detail["founders"] = ", ".join(founder_names)

        except Exception as e:
            logger.debug(f"YC detail scrape failed for {href}: {e}")
        finally:
            await page.close()

        return detail

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

            # First pass: collect card-level data and filter
            card_data = []
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

                    card_data.append(
                        {
                            "href": href,
                            "name": name.strip(),
                            "description": description.strip(),
                            "batch": batch.strip(),
                            "founded_year": founded_year,
                            "tags": category_tag or "Consumer",
                            "logo_url": logo or "",
                        }
                    )
                except Exception as e:
                    errors.append(str(e))
                    logger.warning(f"YC card parse error: {e}")

            # Second pass: visit each company detail page for website + founders
            logger.info(
                f"YC: Scraping detail pages for {len(card_data)} B2C companies..."
            )
            for i, data in enumerate(card_data):
                detail = await self._scrape_company_detail(context, data["href"])
                companies.append(
                    {
                        "name": data["name"],
                        "description": data["description"],
                        "website": detail["website"]
                        or f"https://www.ycombinator.com{data['href']}",
                        "founders": detail["founders"],
                        "linkedin_url": detail["linkedin_url"],
                        "accelerator": "YC",
                        "batch": data["batch"],
                        "founded_year": data["founded_year"],
                        "tags": data["tags"],
                        "logo_url": data["logo_url"],
                    }
                )
                if (i + 1) % 10 == 0:
                    logger.info(f"YC: Scraped {i + 1}/{len(card_data)} detail pages")

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
