from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, OutreachLog
from app.schemas import CompanyOut, CompanyUpdate, OutreachLogCreate, OutreachLogOut

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyOut])
def list_companies(
    accelerator: str | None = Query(None),
    batch: str | None = Query(None),
    outreach_done: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if accelerator:
        q = q.filter(Company.accelerator == accelerator)
    if batch:
        q = q.filter(Company.batch == batch)
    if outreach_done is not None:
        q = q.filter(Company.outreach_done == outreach_done)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))
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
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Company not found")
    if data.outreach_done is not None:
        company.outreach_done = data.outreach_done
    if data.notes is not None:
        company.notes = data.notes
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
