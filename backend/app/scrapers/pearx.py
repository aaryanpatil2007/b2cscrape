"""PearX / Pear VC scraper — uses WordPress REST API directly.

Pear VC has a public WP REST API with a 'Consumer' sector taxonomy (ID=6).
We paginate through all consumer companies without needing Playwright rendering.
"""

import json
import logging

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Consumer sector taxonomy ID on Pear VC's WordPress site
CONSUMER_SECTOR_ID = 6
API_BASE = "https://www.pear.vc/wp-json/wp/v2/pear_vc_company"


class PearXScraper(BaseScraper):
    source_name = "PearX"

    async def scrape(self) -> list[dict]:
        pw, browser, context, page = await self._launch_browser()
        companies = []

        try:
            page_num = 1
            while True:
                url = (
                    f"{API_BASE}"
                    f"?pear_vc_company_sector={CONSUMER_SECTOR_ID}"
                    f"&per_page=100&page={page_num}"
                )
                try:
                    await self._safe_goto(page, url)
                    await page.wait_for_timeout(1000)
                    body = await page.inner_text("body")
                    results = json.loads(body)
                except Exception:
                    break  # 400 = past last page

                if not isinstance(results, list) or len(results) == 0:
                    break

                for co in results:
                    title_obj = co.get("title", {})
                    name = title_obj.get("rendered", "").strip()
                    if not name:
                        continue

                    meta = co.get("meta", {})
                    website = (
                        meta.get("_links_to", "")
                        or meta.get("website_url", "")
                        or co.get("link", "")
                    )
                    description = (meta.get("short_description", "") or "").strip()
                    # PearX API content field is page template HTML, not useful
                    # Only use short_description if it looks like text, not a URL
                    if description.startswith("http"):
                        description = ""

                    linkedin_url = meta.get("linkedin_url", "") or ""
                    logo_id = meta.get("logo", "")
                    headquarters = meta.get("headquarters", "") or ""

                    companies.append(
                        {
                            "name": name,
                            "description": description[:500],
                            "website": website,
                            "founders": "",
                            "linkedin_url": linkedin_url,
                            "accelerator": "PearX",
                            "batch": "",
                            "founded_year": None,
                            "tags": "Consumer",
                            "logo_url": "",  # would need extra API call per logo
                        }
                    )

                page_num += 1

        except Exception as e:
            logger.error(f"PearX scrape error: {e}")
        finally:
            await browser.close()
            await pw.stop()

        logger.info(f"PearX: Got {len(companies)} consumer companies via API")
        return companies
