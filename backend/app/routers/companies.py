import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Company, OutreachLog
from app.schemas import (
    CompanyOut,
    CompanyUpdate,
    EnrichResult,
    OutreachLogCreate,
    OutreachLogOut,
    SendEmailRequest,
    SendEmailResult,
)

logger = logging.getLogger(__name__)

# Email domains to reject — social/generic, not founder emails
JUNK_EMAIL_DOMAINS = {
    "youtube.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "tiktok.com", "linkedin.com", "pinterest.com", "snapchat.com", "reddit.com",
    "medium.com", "github.com", "apple.com", "google.com", "gmail.com",
    "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "ycombinator.com",
    "startupschool.org", "example.com",
}


def _is_junk_email(email: str) -> bool:
    """Check if email is from a social/generic domain."""
    if not email or "@" not in email:
        return True
    domain = email.split("@")[1].lower()
    return domain in JUNK_EMAIL_DOMAINS


router = APIRouter(prefix="/api/companies", tags=["companies"])

# Aliases so users can type "yc" or "y combinator" etc.
ACCELERATOR_ALIASES = {
    "yc": "YC",
    "y combinator": "YC",
    "a16z": "a16z Speedrun",
    "a16z speedrun": "a16z Speedrun",
    "pearx": "PearX",
    "pear": "PearX",
    "grin": "GRIN Client",
    "bazaarvoice": "Bazaarvoice Client",
    "aspire": "Aspire Client",
    "hashtagpaid": "#paid Client",
    "#paid": "#paid Client",
    "nosto": "Nosto Client",
    "archive": "Archive Client",
}

# Batch patterns like S24, W23, F21, etc.
BATCH_PATTERN = re.compile(r"^[swf]\d{2}$", re.IGNORECASE)


def _parse_smart_search(search: str):
    """Parse a search string into structured filters.

    Returns (accelerator, batch, remaining_text) where any can be None/empty.
    Examples:
        "yc s24"       -> ("Y Combinator", "S24", "")
        "a16z"         -> ("a16z Speedrun", None, "")
        "yc fintech"   -> ("Y Combinator", None, "fintech")
        "stripe"       -> (None, None, "stripe")
    """
    tokens = search.strip().lower().split()
    accelerator = None
    batch = None
    remaining = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Check two-word aliases first (e.g. "y combinator")
        if i + 1 < len(tokens):
            two_word = f"{token} {tokens[i + 1]}"
            if two_word in ACCELERATOR_ALIASES:
                accelerator = ACCELERATOR_ALIASES[two_word]
                i += 2
                continue

        # Single-word alias
        if token in ACCELERATOR_ALIASES and accelerator is None:
            accelerator = ACCELERATOR_ALIASES[token]
            i += 1
            continue

        # Batch pattern
        if BATCH_PATTERN.match(token) and batch is None:
            batch = token.upper()
            i += 1
            continue

        remaining.append(token)
        i += 1

    return accelerator, batch, " ".join(remaining)


@router.get("/", response_model=list[CompanyOut])
def list_companies(
    accelerator: str | None = Query(None),
    batch: str | None = Query(None),
    outreach_done: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Company)

    # Smart search: parse tokens for accelerator, batch, and name keywords
    parsed_accel = None
    parsed_batch = None
    text_search = None
    if search:
        parsed_accel, parsed_batch, text_search = _parse_smart_search(search)

    # Explicit dropdown filters take priority over parsed ones
    eff_accel = accelerator or parsed_accel
    eff_batch = batch or parsed_batch

    if eff_accel:
        q = q.filter(Company.accelerator.ilike(f"%{eff_accel}%"))
    if eff_batch:
        q = q.filter(Company.batch.ilike(f"%{eff_batch}%"))
    if outreach_done is not None:
        q = q.filter(Company.outreach_done == outreach_done)
    if text_search:
        like = f"%{text_search}%"
        q = q.filter(
            or_(
                Company.name.ilike(like),
                Company.description.ilike(like),
                Company.tags.ilike(like),
            )
        )
    return q.order_by(desc(Company.scraped_at)).all()


@router.get("/filters")
def get_filters(db: Session = Depends(get_db)):
    accelerators = [
        r[0]
        for r in db.query(Company.accelerator).distinct().all()
        if r[0]
    ]
    batches = [
        r[0]
        for r in db.query(Company.batch).distinct().order_by(desc(Company.batch)).all()
        if r[0]
    ]
    return {"accelerators": sorted(accelerators), "batches": batches}


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int, data: CompanyUpdate, db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if data.outreach_done is not None:
        company.outreach_done = data.outreach_done
    if data.notes is not None:
        company.notes = data.notes
    if data.founder_email is not None:
        company.founder_email = data.founder_email
    db.commit()
    db.refresh(company)
    return company


@router.post("/outreach-log", response_model=OutreachLogOut)
def add_outreach_log(data: OutreachLogCreate, db: Session = Depends(get_db)):
    log = OutreachLog(**data.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/{company_id}/outreach-logs", response_model=list[OutreachLogOut])
def get_outreach_logs(company_id: int, db: Session = Depends(get_db)):
    return (
        db.query(OutreachLog)
        .filter(OutreachLog.company_id == company_id)
        .order_by(desc(OutreachLog.created_at))
        .all()
    )


@router.delete("/all")
def delete_all_companies(db: Session = Depends(get_db)):
    db.query(OutreachLog).delete()
    count = db.query(Company).delete()
    db.commit()
    return {"deleted": count}


# --------------- Hunter.io Email Enrichment ---------------


def _extract_domain(website: str) -> str:
    """Pull domain from a URL like 'https://www.example.com/page' -> 'example.com'."""
    from urllib.parse import urlparse

    if not website:
        return ""
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"
    parsed = urlparse(website)
    host = parsed.hostname or ""
    # Strip www.
    if host.startswith("www."):
        host = host[4:]
    return host


async def _hunter_find_email(domain: str, first_name: str, last_name: str) -> dict:
    """Call Hunter.io email-finder to get an email for a person at a domain."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": settings.hunter_api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "email": data.get("email", ""),
            "score": data.get("score", 0),
        }


async def _hunter_domain_search(domain: str) -> list[dict]:
    """Call Hunter.io domain-search to find emails associated with a domain."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": settings.hunter_api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return data.get("emails", [])


async def _hunter_verify_email(email: str) -> dict:
    """Call Hunter.io email-verifier."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={
                "email": email,
                "api_key": settings.hunter_api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "status": data.get("status", "unknown"),
            "result": data.get("result", "unknown"),
        }


@router.post("/{company_id}/enrich", response_model=EnrichResult)
async def enrich_company_email(company_id: int, db: Session = Depends(get_db)):
    """Find and verify an email for a company's founder using Hunter.io."""
    if not settings.hunter_api_key:
        raise HTTPException(status_code=400, detail="HUNTER_API_KEY not configured")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    domain = _extract_domain(company.website)
    if not domain:
        return EnrichResult(
            company_id=company_id, error="No website domain available"
        )

    email = ""
    verified = False

    # Strategy 1: If we have founder names, use email-finder
    if company.founders:
        # Take the first founder name
        first_founder = company.founders.split(",")[0].strip()
        parts = first_founder.split()
        if len(parts) >= 2:
            first_name, last_name = parts[0], parts[-1]
            try:
                result = await _hunter_find_email(domain, first_name, last_name)
                candidate = result.get("email", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
            except Exception as e:
                logger.warning(f"Hunter email-finder failed for {domain}: {e}")

    # Strategy 2: Fall back to domain search — pick first non-junk
    if not email:
        try:
            emails = await _hunter_domain_search(domain)
            for entry in emails:
                candidate = entry.get("value", "")
                if candidate and not _is_junk_email(candidate):
                    email = candidate
                    break
        except Exception as e:
            logger.warning(f"Hunter domain-search failed for {domain}: {e}")

    if not email:
        return EnrichResult(
            company_id=company_id, error="No email found via Hunter.io"
        )

    # Verify the email
    try:
        verification = await _hunter_verify_email(email)
        verified = verification.get("result") == "deliverable"
    except Exception as e:
        logger.warning(f"Hunter verify failed for {email}: {e}")

    # Save to DB
    company.founder_email = email
    company.email_verified = verified
    db.commit()

    return EnrichResult(company_id=company_id, email=email, verified=verified)


@router.post("/enrich-all", response_model=list[EnrichResult])
async def enrich_all_emails(db: Session = Depends(get_db)):
    """Enrich emails for all companies that don't have one yet."""
    if not settings.hunter_api_key:
        raise HTTPException(status_code=400, detail="HUNTER_API_KEY not configured")

    companies = (
        db.query(Company)
        .filter(Company.founder_email == "")
        .filter(Company.website != "")
        .all()
    )

    results = []
    for company in companies:
        try:
            result = await enrich_company_email(company.id, db)
            results.append(result)
        except Exception as e:
            results.append(
                EnrichResult(company_id=company.id, error=str(e))
            )

    return results


# --------------- Email Sending ---------------


@router.post("/{company_id}/send-email", response_model=SendEmailResult)
def send_email(
    company_id: int,
    req: SendEmailRequest,
    db: Session = Depends(get_db),
):
    """Send an email to a company's founder and log it as outreach."""
    if not settings.smtp_host:
        raise HTTPException(status_code=400, detail="SMTP not configured")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not company.founder_email:
        raise HTTPException(
            status_code=400, detail="No email on file — enrich first"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = req.subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = company.founder_email

    # Send as both plain text and HTML
    msg.attach(MIMEText(req.body, "plain"))
    msg.attach(MIMEText(req.body.replace("\n", "<br>"), "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"SMTP send failed for {company.founder_email}: {e}")
        return SendEmailResult(success=False, error=str(e))

    # Log the outreach
    log = OutreachLog(
        company_id=company_id,
        action="email_sent",
        details=f"Subject: {req.subject}\nTo: {company.founder_email}",
    )
    db.add(log)
    company.outreach_done = True
    db.commit()

    return SendEmailResult(success=True)
