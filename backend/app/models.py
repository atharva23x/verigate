"""VeriGate database models."""

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


# --------------------------------------------------------------------------- #
# Users / roles (DPDP-style: officer, reviewer, auditor(read-only))
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(24), nullable=False)  # officer | reviewer | auditor
    full_name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=utcnow)


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    ref_no = Column(String(40), unique=True, nullable=False, index=True)
    institution_name = Column(String(256), nullable=False)
    category = Column(String(32), nullable=False)  # Engineering | Management | Pharmacy
    aicte_id = Column(String(48), index=True)
    address = Column(String(512))
    approved_intake = Column(Integer, default=0)
    scenario = Column(String(8), default="")  # seed-time tag: A..E
    status = Column(String(32), default="UPLOADED", index=True)
    # UPLOADED | PROCESSING | VERIFIED | INSUFFICIENT_EVIDENCE | IN_REVIEW | APPROVED | REJECTED
    gate_status = Column(String(32), default="")       # VERIFIED | INSUFFICIENT_EVIDENCE
    gate_reasons = Column(JSON, default=list)          # explainable gate reasons
    gate_confidence = Column(Float, default=0.0)       # 0..1 confidence behind the gate
    risk_score = Column(Float, default=0.0)            # 0..1, drives dashboard ranking
    consistency_score = Column(Float, default=0.0)     # XGBoost cross-record score
    ocr_confidence = Column(Float, default=0.0)        # mean OCR confidence
    tamper_score = Column(Float, default=0.0)          # ELA aggregate
    issuer_status = Column(String(32), default="")     # worst-case issuer status
    checklist_json = Column(JSON, default=list)        # auto-checklist per rules.json
    progress_json = Column(JSON, default=dict)         # live pipeline progress
    created_by = Column(String(64), default="system")
    created_at = Column(DateTime, default=utcnow)
    validated_at = Column(DateTime)

    documents = relationship(
        "Document", back_populates="application", cascade="all, delete-orphan"
    )
    flags = relationship(
        "Flag", back_populates="application", cascade="all, delete-orphan"
    )
    reviews = relationship(
        "ReviewDecision", back_populates="application", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    doc_type = Column(String(64), nullable=False)
    filename = Column(String(256), nullable=False)
    stored_path = Column(String(512), nullable=False)
    mime = Column(String(64), default="application/pdf")
    page_count = Column(Integer, default=1)
    ocr_text = Column(Text, default="")
    ocr_confidence = Column(Float, default=0.0)
    ocr_engine = Column(String(32), default="")
    extracted_json = Column(JSON, default=dict)   # fields with box + confidence
    phash = Column(String(32), default="")
    tamper_score = Column(Float, default=0.0)
    ela_bbox = Column(JSON, default=None)         # normalized [x,y,w,h] or None
    duplicate_of = Column(Integer, default=None)  # document id of the donor copy
    uploaded_at = Column(DateTime, default=utcnow)

    application = relationship("Application", back_populates="documents")


class Flag(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    kind = Column(String(24), nullable=False)   # RULE|OCR|EXTRACTION|CONSISTENCY|TAMPER|DUPLICATE|ISSUER|EVIDENCE
    rule_id = Column(String(40), nullable=False)
    title = Column(String(160), nullable=False)
    reason = Column(Text, default="")
    severity = Column(String(16), default="WARN")  # INFO|WARN|CRITICAL
    page_no = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)  # normalized [x, y, w, h] on that page
    status = Column(String(16), default="OPEN")  # OPEN|RESOLVED
    created_at = Column(DateTime, default=utcnow)

    application = relationship("Application", back_populates="flags")
    document = relationship("Document")
    decisions = relationship(
        "ReviewDecision", back_populates="flag", cascade="all, delete-orphan"
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(Integer, primary_key=True)
    flag_id = Column(Integer, ForeignKey("flags.id"), nullable=False, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=False, index=True
    )
    reviewer_id = Column(Integer, nullable=False)
    reviewer_name = Column(String(128), nullable=False)
    decision = Column(String(20), nullable=False)  # APPROVE | REJECT | REQUEST_INFO
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    flag = relationship("Flag", back_populates="decisions")
    application = relationship("Application", back_populates="reviews")


class AuditLog(Base):
    """Append-only. There is deliberately no update/delete API for this table."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=utcnow, index=True)
    actor = Column(String(64), default="system")
    role = Column(String(24), default="system")
    action = Column(String(48), nullable=False, index=True)
    entity_type = Column(String(32), default="")
    entity_id = Column(Integer, default=None)
    detail = Column(JSON, default=dict)


# --------------------------------------------------------------------------- #
# Mock registries backing the cross-record + issuer checks
# --------------------------------------------------------------------------- #
class MockRecord(Base):
    """Mock AICTE master records table (cross-record consistency source)."""

    __tablename__ = "mock_aicte_records"

    id = Column(Integer, primary_key=True)
    aicte_id = Column(String(48), unique=True, nullable=False, index=True)
    institution_name = Column(String(256), nullable=False)
    category = Column(String(32), nullable=False)
    address = Column(String(512), default="")
    approved_intake = Column(Integer, default=0)
    status = Column(String(32), default="APPROVED")
    valid_upto = Column(String(16), default="31-03-2028")


class IssuerRecord(Base):
    """Mock issuer portal registry: UGC / State board / Fire dept / Pharmacy council."""

    __tablename__ = "issuer_records"

    id = Column(Integer, primary_key=True)
    portal = Column(String(32), nullable=False, index=True)
    doc_number = Column(String(48), nullable=False, index=True)
    holder_name = Column(String(256), nullable=False)
    qr_token = Column(String(32), default="")
    signature = Column(String(64), default="")  # HMAC over portal|doc_number|qr
    issue_date = Column(String(16), default="")
    valid_upto = Column(String(16), default="")
    # Simulated portal outage for this specific record (demo scenario D)
    source_unavailable = Column(Boolean, default=False)
