from datetime import datetime

from pydantic import BaseModel


class CompanyBase(BaseModel):
    name: str
    description: str = ""
    website: str = ""
    founders: str = ""
    linkedin_url: str = ""
    accelerator: str = ""
    batch: str = ""
    founded_year: int | None = None
    tags: str = ""
    logo_url: str = ""


class CompanyOut(CompanyBase):
    id: int
    founder_email: str = ""
    email_verified: bool = False
    outreach_done: bool = False
    notes: str = ""
    scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanyUpdate(BaseModel):
    outreach_done: bool | None = None
    notes: str | None = None
    founder_email: str | None = None


class EnrichResult(BaseModel):
    company_id: int
    email: str = ""
    verified: bool = False
    error: str = ""


class SendEmailRequest(BaseModel):
    subject: str
    body: str


class SendEmailResult(BaseModel):
    success: bool
    error: str = ""


class OutreachLogCreate(BaseModel):
    company_id: int
    action: str
    details: str = ""


class OutreachLogOut(BaseModel):
    id: int
    company_id: int
    action: str
    details: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScrapeRequest(BaseModel):
    sources: list[str] = ["yc", "a16z", "pearx"]
    years_back: int = 1
    headless: bool = True


class ScrapeResult(BaseModel):
    source: str
    new_companies: int
    skipped_duplicates: int
    errors: list[str] = []
