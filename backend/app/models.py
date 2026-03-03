import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(512), nullable=False)
    description = Column(Text, default="")
    website = Column(String(1024), default="")
    founders = Column(Text, default="")
    linkedin_url = Column(String(1024), default="")
    accelerator = Column(String(128), nullable=False)
    batch = Column(String(64), default="")
    founded_year = Column(Integer, nullable=True)
    tags = Column(Text, default="")
    logo_url = Column(String(1024), default="")
    outreach_done = Column(Boolean, default=False)
    notes = Column(Text, default="")
    scraped_at = Column(DateTime, default=datetime.datetime.utcnow)

    outreach_logs = relationship(
        "OutreachLog", back_populates="company", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", "accelerator", name="uq_company_accelerator"),
    )


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    action = Column(String(256), nullable=False)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    company = relationship("Company", back_populates="outreach_logs")
