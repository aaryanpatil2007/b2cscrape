import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company
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
            skip_count += 1
            continue

        try:
            sp = db.begin_nested()  # savepoint so failure doesn't nuke batch
            company = Company(**data)
            db.add(company)
            db.flush()
            new_count += 1
        except Exception:
            sp.rollback()
            skip_count += 1

    db.commit()
    return new_count, skip_count


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

    return results
