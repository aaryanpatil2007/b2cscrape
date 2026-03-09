import asyncio
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import Company
from app.routers.companies import (
    _extract_domain,
    _hunter_domain_search,
    _hunter_find_email,
    _hunter_verify_email,
)
from app.schemas import ScrapeRequest, ScrapeResult
from app.scrapers.a16z import A16ZScraper
from app.scrapers.competitors.archive import ArchiveScraper
from app.scrapers.competitors.aspire import AspireScraper
from app.scrapers.competitors.bazaarvoice import BazaarvoiceScraper
from app.scrapers.competitors.grin import GRINScraper
from app.scrapers.competitors.hashtagpaid import HashtagPaidScraper
from app.scrapers.competitors.nosto import NostoScraper
from app.scrapers.pearx import PearXScraper
from app.scrapers.yc import YCScraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrape", tags=["scraper"])

SCRAPER_MAP = {
    "yc": YCScraper,
    "a16z": A16ZScraper,
    "pearx": PearXScraper,
    "grin": GRINScraper,
    "bazaarvoice": BazaarvoiceScraper,
    "aspire": AspireScraper,
    "hashtagpaid": HashtagPaidScraper,
    "nosto": NostoScraper,
    "archive": ArchiveScraper,
}

# Domains that are NOT real company websites
BAD_DOMAINS = [
    "ycombinator.com",
    "startupschool.org",
    "bookface.ycombinator.com",
]

# Email domains to reject — these are social/generic, not founder emails
JUNK_EMAIL_DOMAINS = {
    "youtube.com",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "linkedin.com",
    "pinterest.com",
    "snapchat.com",
    "reddit.com",
    "medium.com",
    "github.com",
    "apple.com",
    "google.com",
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "ycombinator.com",
    "startupschool.org",
    "example.com",
}


def _is_junk_email(email: str) -> bool:
    """Check if email is from a social/generic domain."""
    if not email or "@" not in email:
        return True
    domain = email.split("@")[1].lower()
    return domain in JUNK_EMAIL_DOMAINS


def _has_bad_email(company: Company) -> bool:
    """Check if a company has no email or a wrong one (e.g. YC partner, social)."""
    if not company.founder_email:
        return True
    return _is_junk_email(company.founder_email)


def _has_bad_website(website: str) -> bool:
    """Check if a website URL points to YC instead of the real company."""
    if not website:
        return True
    return any(d in website for d in BAD_DOMAINS)


def _upsert_companies(db: Session, companies: list[dict]) -> tuple[int, int]:
    new_count = 0
    skip_count = 0
    seen = set()

    for data in companies:
        key = (data["name"], data["accelerator"])
        if key in seen:
            skip_count += 1
            continue
        seen.add(key)

        exists = (
            db.query(Company)
            .filter(
                Company.name == data["name"],
                Company.accelerator == data["accelerator"],
            )
            .first()
        )
        if exists:
            # Update website/founders and clear bad emails
            updated = False
            if data.get("website") and (
                _has_bad_website(exists.website)
            ):
                exists.website = data["website"]
                updated = True
            if data.get("founders") and not exists.founders:
                exists.founders = data["founders"]
                updated = True
            if data.get("linkedin_url") and not exists.linkedin_url:
                exists.linkedin_url = data["linkedin_url"]
                updated = True
            # Clear bad emails so they get re-enriched
            if _has_bad_email(exists) and updated:
                exists.founder_email = ""
                exists.email_verified = False
            if updated:
                db.flush()
            skip_count += 1
            continue

        try:
            sp = db.begin_nested()
            company = Company(**data)
            db.add(company)
            db.flush()
            new_count += 1
        except Exception:
            sp.rollback()
            skip_count += 1

    db.commit()
    return new_count, skip_count


async def _enrich_email(company: Company) -> None:
    """Find and verify email for a single company via Hunter.io."""
    domain = _extract_domain(company.website)
    if not domain or any(d in domain for d in BAD_DOMAINS):
        return

    email = ""

    # Strategy 1: email-finder with founder name
    if company.founders:
        first_founder = company.founders.split(",")[0].strip()
        parts = first_founder.split()
        if len(parts) >= 2:
            try:
                result = await _hunter_find_email(domain, parts[0], parts[-1])
                candidate = result.get("email", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
            except Exception as e:
                logger.debug(f"Hunter email-finder failed for {domain}: {e}")

    # Strategy 2: domain search — pick first non-junk email
    if not email:
        try:
            emails = await _hunter_domain_search(domain)
            for entry in emails:
                candidate = entry.get("value", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
                    break
        except Exception as e:
            logger.debug(f"Hunter domain-search failed for {domain}: {e}")

    if not email:
        return

    # Verify
    verified = False
    try:
        verification = await _hunter_verify_email(email)
        verified = verification.get("result") == "deliverable"
    except Exception as e:
        logger.debug(f"Hunter verify failed for {email}: {e}")

    company.founder_email = email
    company.email_verified = verified


@router.post("/", response_model=list[ScrapeResult])
async def run_scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    results = []

    for source in req.sources:
        source_key = source.lower()
        scraper_cls = SCRAPER_MAP.get(source_key)
        if not scraper_cls:
            results.append(
                ScrapeResult(
                    source=source,
                    new_companies=0,
                    skipped_duplicates=0,
                    errors=[f"Unknown source: {source}"],
                )
            )
            continue

        scraper = scraper_cls(headless=req.headless, years_back=req.years_back)
        errors = []

        try:
            companies = await scraper.scrape()
            new_count, skip_count = _upsert_companies(db, companies)
        except Exception as e:
            logger.error(f"Scrape error for {source}: {e}")
            errors.append(str(e))
            new_count = 0
            skip_count = 0

        results.append(
            ScrapeResult(
                source=scraper.source_name or source,
                new_companies=new_count,
                skipped_duplicates=skip_count,
                errors=errors,
            )
        )

    # Auto-enrich emails in the background (if Hunter key is set)
    if settings.hunter_api_key:
        asyncio.create_task(_background_enrich())

    return results


async def _background_enrich():
    """Enrich emails for all companies missing them, in a separate DB session."""
    db = SessionLocal()
    try:
        to_enrich = (
            db.query(Company)
            .filter(
                (Company.founder_email == "")
                | (Company.founder_email.contains("ycombinator.com"))
            )
            .filter(Company.website != "")
            .all()
        )
        enriched = 0
        for company in to_enrich:
            if _has_bad_website(company.website):
                continue
            try:
                await _enrich_email(company)
                enriched += 1
                # Commit in batches of 5 so results appear progressively
                if enriched % 5 == 0:
                    db.commit()
            except Exception as e:
                logger.debug(f"Enrich failed for {company.name}: {e}")
        db.commit()
        logger.info(f"Background enrichment done: {enriched} companies enriched")
    except Exception as e:
        logger.error(f"Background enrichment error: {e}")
    finally:
        db.close()
