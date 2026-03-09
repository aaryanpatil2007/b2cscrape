"""Live accelerator search — scrape on-the-fly via Playwright, stream results via SSE."""

import json
import logging
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from playwright.async_api import async_playwright

from app.config import settings
from app.routers.companies import (
    _extract_domain,
    _hunter_domain_search,
    _hunter_find_email,
    _hunter_verify_email,
)
from app.routers.scraper import JUNK_EMAIL_DOMAINS
from app.schemas import SearchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

ACCELERATOR_CONFIGS = {
    "yc": {"name": "Y Combinator", "type": "yc"},
    "y combinator": {"name": "Y Combinator", "type": "yc"},
    "a16z": {"name": "a16z", "type": "a16z"},
    "a16z speedrun": {"name": "a16z", "type": "a16z"},
    "pearx": {"name": "PearX", "type": "pearx"},
}

BATCH_PATTERN = re.compile(r"^[swf]\d{2}$", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"^20\d{2}$")
SEASON_MAP = {"winter": "W", "summer": "S", "fall": "F", "spring": "S"}

# Domains to skip when extracting company website from YC detail page
SKIP_DOMAINS = [
    "ycombinator.com", "startupschool.org", "bookface.ycombinator.com",
    "news.ycombinator.com", "account.ycombinator.com",
    "linkedin.com", "twitter.com", "x.com", "facebook.com",
    "crunchbase.com", "github.com",
]


def _is_junk_email(email: str) -> bool:
    if not email or "@" not in email:
        return True
    return email.split("@")[1].lower() in JUNK_EMAIL_DOMAINS


def _parse_search_query(query: str):
    tokens = query.strip().lower().split()
    accel_config = None
    year = None
    batch = None
    keywords = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if i + 1 < len(tokens):
            two = f"{token} {tokens[i + 1]}"
            if two in ACCELERATOR_CONFIGS and not accel_config:
                accel_config = ACCELERATOR_CONFIGS[two]
                i += 2
                continue
        if token in ACCELERATOR_CONFIGS and not accel_config:
            accel_config = ACCELERATOR_CONFIGS[token]
            i += 1
            continue
        if BATCH_PATTERN.match(token) and not batch:
            batch = token.upper()
            i += 1
            continue
        if YEAR_PATTERN.match(token) and not year:
            year = token
            i += 1
            continue
        if token in SEASON_MAP and not batch:
            if i + 1 < len(tokens) and YEAR_PATTERN.match(tokens[i + 1]):
                batch = f"{SEASON_MAP[token]}{tokens[i + 1][2:]}"
                i += 2
                continue
        keywords.append(token)
        i += 1

    return accel_config, year, batch, " ".join(keywords)


async def _scrape_yc_detail(context, href: str) -> dict:
    """Visit a single YC company page to get real website + founders."""
    detail = {"website": "", "founders": "", "linkedin_url": ""}
    page = await context.new_page()
    try:
        url = f"https://www.ycombinator.com{href}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1500)

        # Domains to also skip (social media links on the page)
        SOCIAL_DOMAINS = [
            "instagram.com", "youtube.com", "tiktok.com",
            "pinterest.com", "snapchat.com", "reddit.com",
            "medium.com", "discord.gg", "discord.com",
            "character.ai", "apps.apple.com", "play.google.com",
        ]
        all_skip = SKIP_DOMAINS + SOCIAL_DOMAINS

        links = await page.query_selector_all("a[href^='http']")
        for link in links:
            link_href = await link.get_attribute("href") or ""
            try:
                link_text = (await link.inner_text()).strip().lower()
            except Exception:
                continue
            if "linkedin.com" in link_href and not detail["linkedin_url"]:
                detail["linkedin_url"] = link_href
            if any(d in link_href for d in all_skip):
                continue
            if re.match(r"^[a-z0-9][\w.-]+\.[a-z]{2,}$", link_text):
                detail["website"] = link_href
                break

        if not detail["website"]:
            all_links = await page.query_selector_all("a[href^='http']")
            for link in all_links[25:]:
                link_href = await link.get_attribute("href") or ""
                if any(d in link_href for d in all_skip):
                    continue
                detail["website"] = link_href
                break

        page_text = await page.inner_text("body")
        founder_names = []
        founders_match = re.search(
            r"(?:Active\s+)?Founders?\s*\n((?:[^\n]+\n){1,10})",
            page_text, re.IGNORECASE,
        )
        if founders_match:
            for line in founders_match.group(1).split("\n"):
                line = line.strip()
                if not line:
                    continue
                if (
                    re.match(r"^[A-Z][a-z]+ [A-Z]", line)
                    and len(line.split()) <= 5
                    and len(line) < 50
                ):
                    founder_names.append(line)
                elif founder_names:
                    break
        detail["founders"] = ", ".join(founder_names)

    except Exception as e:
        logger.debug(f"Detail scrape failed for {href}: {e}")
    finally:
        await page.close()
    return detail


# Track whether we've exhausted Hunter credits this session
_hunter_credits_exhausted = False


async def _check_hunter_credits() -> bool:
    """Return True if we still have Hunter.io credits."""
    global _hunter_credits_exhausted
    if _hunter_credits_exhausted:
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/account",
                params={"api_key": settings.hunter_api_key},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            reqs = data.get("requests", {})
            searches = reqs.get("searches", {})
            available = searches.get("available", 0)
            used = searches.get("used", 0)
            remaining = available - used
            if remaining <= 0:
                _hunter_credits_exhausted = True
                logger.info(f"Hunter.io credits exhausted ({used}/{available} searches used)")
                return False
            logger.info(f"Hunter.io credits: {remaining} searches remaining")
            return True
    except Exception:
        return True  # Assume OK if we can't check


async def _enrich_email_for_result(company: dict) -> dict:
    """Find email via Hunter.io for a search result dict."""
    global _hunter_credits_exhausted

    if not settings.hunter_api_key or _hunter_credits_exhausted:
        return company

    domain = _extract_domain(company.get("website", ""))
    # Skip YC pages, social domains, etc.
    BAD_ENRICH_DOMAINS = SKIP_DOMAINS + [
        "instagram.com", "youtube.com", "tiktok.com",
        "pinterest.com", "snapchat.com", "reddit.com",
        "medium.com", "discord.gg", "discord.com",
        "apps.apple.com", "play.google.com",
    ]
    if not domain or any(d in domain for d in BAD_ENRICH_DOMAINS):
        return company

    email = ""

    # Strategy 1: email-finder with founder name
    founders = company.get("founders", "")
    if founders:
        first_founder = founders.split(",")[0].strip()
        parts = first_founder.split()
        if len(parts) >= 2:
            try:
                result = await _hunter_find_email(domain, parts[0], parts[-1])
                candidate = result.get("email", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
            except Exception as e:
                if "429" in str(e) or "402" in str(e):
                    _hunter_credits_exhausted = True
                    logger.info("Hunter.io credits exhausted (rate limited)")
                    return company
                logger.debug(f"Hunter email-finder error for {domain}: {e}")

    # Strategy 2: domain search
    if not email:
        try:
            emails = await _hunter_domain_search(domain)
            for entry in emails:
                candidate = entry.get("value", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
                    break
        except Exception as e:
            if "429" in str(e) or "402" in str(e):
                _hunter_credits_exhausted = True
                logger.info("Hunter.io credits exhausted (rate limited)")
                return company
            logger.debug(f"Hunter domain-search error for {domain}: {e}")

    if not email:
        return company

    # Verify (skip if no verification credits)
    verified = False
    try:
        verification = await _hunter_verify_email(email)
        verified = verification.get("result") == "deliverable"
    except Exception:
        pass  # Verification is optional, keep the email

    company["founder_email"] = email
    company["email_verified"] = verified
    return company


async def _yc_search_stream(year, batch, keywords):
    """Generator that yields SSE events for each YC company found + enriched."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    )
    page = await context.new_page()

    try:
        # Build URL
        params = []
        if batch:
            prefix_map = {"S": "Summer", "W": "Winter", "F": "Fall"}
            season = prefix_map.get(batch[0], "")
            yr = f"20{batch[1:]}"
            if season:
                params.append(f"batch={season}+{yr}")
        elif year:
            params.append(f"batch=Winter+{year}")
        if keywords:
            params.append(f"query={keywords}")

        url = "https://www.ycombinator.com/companies"
        if params:
            url += "?" + "&".join(params)

        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # Scroll to load
        prev_count = 0
        for _ in range(20):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(800)
            cards = await page.query_selector_all("a[href^='/companies/']")
            if len(cards) == prev_count:
                break
            prev_count = len(cards)

        cards = await page.query_selector_all("a[href^='/companies/']")
        seen = set()
        card_list = []

        # First: collect all cards from the listing page
        for card in cards:
            try:
                href = await card.get_attribute("href")
                if not href or href in seen or "/companies?" in href:
                    continue
                if href in ("/companies", "/companies/"):
                    continue
                seen.add(href)

                all_text = await card.inner_text()
                lines = [l.strip() for l in all_text.split("\n") if l.strip()]

                name_el = await card.query_selector("span.text-lg, span[class*='coName']")
                name = await name_el.inner_text() if name_el else ""
                if not name:
                    name = lines[0] if lines else ""
                if not name:
                    continue

                card_batch = ""
                m = re.search(r"\b(SPRING|SUMMER|WINTER|FALL)\s+(20\d{2})\b", all_text, re.IGNORECASE)
                m2 = re.search(r"\b([SWF]\d{2})\b", all_text)
                if m:
                    card_batch = f"{m.group(1)[0].upper()}{m.group(2)[2:]}"
                elif m2:
                    card_batch = m2.group(1)

                desc_el = await card.query_selector("span.text-sm, span[class*='coDescription']")
                description = await desc_el.inner_text() if desc_el else ""
                if not description:
                    for line in lines:
                        if line == name or (len(line) < 15 and line.isupper()):
                            continue
                        if len(line) > len(description):
                            description = line

                img_el = await card.query_selector("img")
                logo = await img_el.get_attribute("src") if img_el else ""

                card_list.append({
                    "href": href,
                    "name": name.strip(),
                    "description": description.strip(),
                    "batch": card_batch,
                    "logo_url": logo or "",
                })
            except Exception:
                continue

        # Check Hunter credits before starting enrichment
        has_credits = await _check_hunter_credits() if settings.hunter_api_key else False

        # Send total count + credit status
        yield f"data: {json.dumps({'type': 'total', 'count': len(card_list), 'hunter_credits': has_credits})}\n\n"

        # Now process each: detail page + email enrichment, stream each result
        for i, cd in enumerate(card_list):
            try:
                detail = await _scrape_yc_detail(context, cd["href"])

                result = {
                    "name": cd["name"],
                    "description": cd["description"],
                    "website": detail["website"] or f"https://www.ycombinator.com{cd['href']}",
                    "founders": detail["founders"],
                    "batch": cd["batch"],
                    "tags": "YC",
                    "logo_url": cd["logo_url"],
                    "source_url": f"https://www.ycombinator.com{cd['href']}",
                    "founder_email": "",
                    "email_verified": False,
                }

                # Enrich email
                result = await _enrich_email_for_result(result)

                yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"

            except Exception as e:
                logger.debug(f"Error processing {cd['name']}: {e}")
                # Still send what we have
                result = {
                    "name": cd["name"],
                    "description": cd["description"],
                    "website": "",
                    "founders": "",
                    "batch": cd["batch"],
                    "tags": "YC",
                    "logo_url": cd["logo_url"],
                    "source_url": f"https://www.ycombinator.com{cd['href']}",
                    "founder_email": "",
                    "email_verified": False,
                }
                yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    finally:
        await browser.close()
        await pw.stop()


@router.post("/")
async def search_accelerator(req: SearchRequest):
    """Live search accelerator portfolios — returns SSE stream."""
    accel_config, year, batch, keywords = _parse_search_query(req.query)

    if not accel_config:
        # Default to YC if no accelerator specified
        accel_config = ACCELERATOR_CONFIGS["yc"]

    accel_type = accel_config["type"]

    if accel_type == "yc":
        return StreamingResponse(
            _yc_search_stream(year, batch, keywords),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # For other accelerators, fall back to non-streaming for now
    # (can add streaming for a16z, pearx later)
    return StreamingResponse(
        _yc_search_stream(year, batch, keywords),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
