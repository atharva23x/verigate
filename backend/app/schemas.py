"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    full_name: str


# ------------------------------------------------------------- applications
class ApplicationCreate(BaseModel):
    institution_name: str = Field(min_length=3, max_length=256)
    category: str  # Engineering | Management | Pharmacy
    aicte_id: str = ""
    address: str = ""
    approved_intake: int = 0


class BBox(BaseModel):
    """Normalized (0..1) bounding box: x, y, width, height - top-left origin."""

    x: float
    y: float
    w: float
    h: float


class ExtractedField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0
    page_no: Optional[int] = None
    bbox: Optional[list[float]] = None


class DocumentOut(BaseModel):
    id: int
    doc_type: str
    filename: str
    mime: str
    page_count: int
    ocr_confidence: float
    ocr_engine: str
    ocr_text: str
    extracted_json: dict[str, Any]
    tamper_score: float
    ela_bbox: Optional[list[float]]
    phash: str
    duplicate_of: Optional[int]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class FlagOut(BaseModel):
    id: int
    application_id: int
    document_id: Optional[int]
    kind: str
    rule_id: str
    title: str
    reason: str
    severity: str
    page_no: Optional[int]
    bbox: Optional[list[float]]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationSummary(BaseModel):
    id: int
    ref_no: str
    institution_name: str
    category: str
    aicte_id: str
    status: str
    gate_status: str
    gate_confidence: float
    risk_score: float
    consistency_score: float
    ocr_confidence: float
    tamper_score: float
    issuer_status: str
    open_flags: int = 0
    doc_count: int = 0
    scenario: str = ""  # seed-time demo tag (A..E), shown as a badge in the UI
    created_at: datetime
    validated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApplicationDetail(ApplicationSummary):
    address: str
    approved_intake: int
    scenario: str
    gate_reasons: list[Any]
    checklist_json: list[Any]
    progress_json: dict[str, Any]
    created_by: str
    documents: list[DocumentOut]
    flags: list[FlagOut]
    reviews: list[Any] = []  # populated with plain dicts by the router


class DocumentUploaded(BaseModel):
    id: int
    filename: str
    doc_type: str


# ------------------------------------------------------------------ reviews
class DecisionRequest(BaseModel):
    decision: str  # APPROVE | REJECT | REQUEST_INFO
    comment: str = ""


class DecisionOut(BaseModel):
    id: int
    flag_id: int
    application_id: int
    reviewer_name: str
    decision: str
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- audit log
class AuditEntryOut(BaseModel):
    id: int
    ts: datetime
    actor: str
    role: str
    action: str
    entity_type: str
    entity_id: Optional[int]
    detail: dict[str, Any]

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total: int
    verified: int
    insufficient_evidence: int
    in_review: int
    approved: int
    rejected: int
    processing: int
    gate_pass_rate: float
    by_category: dict[str, int]
    mock_mode: bool
