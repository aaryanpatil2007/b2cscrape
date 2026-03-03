"""a16z Speedrun scraper — uses public REST API directly."""

import logging
from urllib.parse import urlencode

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://speedrun-be.a16z.com/api/companies/companies/"

# Industry tags from a16z that are consumer-facing
CONSUMER_INDUSTRIES = {
    "dating",
    "fitness",
    "games studio",
    "social networking",
    "ugc",
    "real money gaming",
    "media/animation",
    "marketplace",
    "edtech",
    "publishing",
    "ar/vr",
    "creative tools",
    "advertising/marketing",
}

# Industries that are clearly NOT consumer
B2B_INDUSTRIES = {
    "b2b",
    "defense tech",
    "developer tools",
    "ai models/infrastructure",
    "robotics",
    "deep tech",
}


class A16ZScraper(BaseScraper):
    source_name = "a16z Speedrun"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []
        skipped = 0

        try:
            # Fetch all companies via the public API
            params = urlencode({"limit": 200, "offset": 0, "ordering": "name"})
            url = f"{API_URL}?{params}"
            await self._safe_goto(page, url)
            await page.wait_for_timeout(2000)

            # Parse JSON response from the page
            import json
            body = await page.inner_text("body")
            data = json.loads(body)
            results = data.get("results", [])
            logger.info(f"a16z API: Got {len(results)} companies")

            for co in results:
                name = co.get("name", "").strip()
                if not name:
                    continue

                industries = [i.lower() for i in co.get("industries", [])]

                # Filter: keep consumer-oriented companies, skip clear B2B
                is_consumer = any(i in CONSUMER_INDUSTRIES for i in industries)
                is_b2b = any(i in B2B_INDUSTRIES for i in industries)

                # For ambiguous ones (AI, Fintech, Healthcare, Web3) check
                # if they also have a consumer tag or lean consumer
                if not is_consumer and is_b2b:
                    skipped += 1
                    continue

                if not is_consumer and not is_b2b:
                    # Ambiguous — check description for consumer signals
                    from app.scrapers.consumer_filter import is_consumer_company
                    desc = co.get("preamble", "") or co.get("description", "")
                    industry_text = " ".join(co.get("industries", []))
                    if not is_consumer_company(industry_text, desc):
                        skipped += 1
                        continue

                # Extract founder names
                founders = []
                for f in co.get("founder_set", []):
                    first = f.get("first_name", "")
                    last = f.get("last_name", "")
                    if first or last:
                        founders.append(f"{first} {last}".strip())

                # Extract founder LinkedIn URLs
                linkedin_urls = []
                for f in co.get("founder_set", []):
                    li = f.get("linkedin_url", "")
                    if li:
                        linkedin_urls.append(li)

                cohort = co.get("cohort", "")
                founded_year = co.get("founded_year")
                if founded_year and founded_year < self.cutoff_year:
                    continue

                companies.append(
                    {
                        "name": name,
                        "description": (co.get("preamble", "") or "").strip()[:500],
                        "website": co.get("website_url", "") or "",
                        "founders": ", ".join(founders),
                        "linkedin_url": "; ".join(linkedin_urls),
                        "accelerator": "a16z Speedrun",
                        "batch": cohort,
                        "founded_year": founded_year,
                        "tags": ", ".join(co.get("industries", [])),
                        "logo_url": co.get("logo", "") or "",
                    }
                )

        except Exception as e:
            logger.error(f"a16z scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"a16z: Kept {len(companies)} B2C, skipped {skipped} non-consumer")
        return companies
