"""Application endpoints: create, upload documents, validate, inspect."""

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import config
from ..audit import audit
from ..database import get_db
from ..models import Application, Document, Flag, ReviewDecision, User
from ..schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    DocumentUploaded,
    FlagOut,
)
from ..security import get_current_user, require_roles
from ..services import pipeline, render

router = APIRouter(tags=["applications"])

CATEGORIES = ("Engineering", "Management", "Pharmacy")

DOC_TYPE_HINTS = [
    ("fire", "FIRE_SAFETY_NOC"),
    ("stability", "BUILDING_STABILITY_CERT"),
    ("structur", "BUILDING_STABILITY_CERT"),
    ("premises", "PREMISES_NOC"),
    ("pharmacy", "PHARMACY_REG_CERT"),
    ("pci", "PHARMACY_REG_CERT"),
    ("lease", "LEASE_DEED"),
    ("land", "LAND_OWNERSHIP_DEED"),
    ("affidavit", "AFFIDAVIT_UNDERTAKING"),
    ("previous", "PREV_EOA_LETTER"),
    ("approval", "PREV_EOA_LETTER"),
    ("eoa", "EOA_FORM"),
    ("form", "EOA_FORM"),
]


def _auto_doc_type(filename: str) -> str:
    low = (filename or "").lower()
    for hint, doc_type in DOC_TYPE_HINTS:
        if hint in low:
            return doc_type
    return "EOA_FORM"


def _mime_for(name: str) -> str:
    low = name.lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(".png"):
        return "image/png"
    if low.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return "application/octet-stream"


# ------------------------------------------------------------------ create
def _next_ref_no(db: Session) -> str:
    """Next free `EoA/2026/NNNN` reference.

    Derived from the *highest* existing number rather than COUNT(*): once an
    officer deletes a middle application, a count-based id would collide with
    an existing UNIQUE ref_no on the next create.
    """
    highest = 0
    for (ref,) in db.query(Application.ref_no).all():
        tail = (ref or "").rsplit("/", 1)[-1]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"EoA/2026/{highest + 1:04d}"


@router.post("/applications", response_model=ApplicationSummary)
def create_application(
    body: ApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("officer")),
):
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {CATEGORIES}")
    app = Application(
        ref_no=_next_ref_no(db),
        institution_name=body.institution_name.strip(),
        category=body.category,
        aicte_id=body.aicte_id.strip(),
        address=body.address.strip(),
        approved_intake=body.approved_intake,
        status="UPLOADED",
        created_by=user.username,
    )
    db.add(app)
    db.commit()
    audit(
        db,
        "APP_CREATE",
        actor=user.username,
        role=user.role,
        entity_type="application",
        entity_id=app.id,
        detail={"ref_no": app.ref_no, "category": app.category},
    )
    return _summary(db, app)


# ------------------------------------------------------------------ upload
@router.post(
    "/applications/{app_id}/documents", response_model=list[DocumentUploaded]
)
async def upload_documents(
    app_id: int,
    files: list[UploadFile] = File(...),
    doc_types: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("officer")),
):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    if not files:
        raise HTTPException(400, "At least one file is required")

    try:
        type_list = json.loads(doc_types) if doc_types.strip() else []
    except json.JSONDecodeError:
        type_list = []

    target = config.UPLOAD_DIR / f"app_{app_id}"
    target.mkdir(parents=True, exist_ok=True)

    uploaded: list[DocumentUploaded] = []
    for i, f in enumerate(files):
        doc_type = (
            type_list[i]
            if i < len(type_list) and type_list[i]
            else _auto_doc_type(f.filename or "")
        )
        safe = Path(f.filename or "upload.pdf").name.replace(" ", "_")
        stored = target / f"{uuid.uuid4().hex[:8]}_{safe}"
        with stored.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        doc = Document(
            application_id=app.id,
            doc_type=doc_type,
            filename=safe,
            stored_path=str(stored),
            mime=_mime_for(safe),
        )
        db.add(doc)
        db.commit()
        uploaded.append(
            DocumentUploaded(id=doc.id, filename=safe, doc_type=doc_type)
        )
    audit(
        db,
        "DOC_UPLOAD",
        actor=user.username,
        role=user.role,
        entity_type="application",
        entity_id=app.id,
        detail={"documents": [u.model_dump() for u in uploaded]},
    )
    return uploaded


# ----------------------------------------------------------------- validate
@router.post("/applications/{app_id}/validate")
def validate_application(
    app_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("officer")),
):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    if not app.documents:
        raise HTTPException(400, "Upload at least one document before validating")
    if app.status == "PROCESSING":
        raise HTTPException(409, "Validation already running")

    app.status = "PROCESSING"
    db.commit()
    audit(
        db,
        "VALIDATE_START",
        actor=user.username,
        role=user.role,
        entity_type="application",
        entity_id=app.id,
        detail={"documents": len(app.documents)},
    )
    background.add_task(pipeline.run_validation, app_id, user.username, True)
    return {"status": "PROCESSING", "app_id": app_id}


# ------------------------------------------------------------------ delete
@router.delete("/applications/{app_id}")
def delete_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("officer")),
):
    """Officer-only cleanup of an application that is no longer needed.

    Removes the application row (cascading to its documents, flags and review
    decisions) plus every file stored for it, then records an APP_DELETE entry.
    The audit log itself is never modified - that is the point of an audit log.
    """
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    if app.status == "PROCESSING":
        raise HTTPException(409, "Validation is still running - try again shortly")

    snapshot = {
        "ref_no": app.ref_no,
        "institution": app.institution_name,
        "category": app.category,
        "status": app.status,
        "documents": len(app.documents),
        "flags": len(app.flags),
    }
    doc_ids = [d.id for d in app.documents]
    upload_dir = config.UPLOAD_DIR / f"app_{app_id}"

    db.delete(app)  # cascade: documents -> flags -> review decisions
    db.commit()

    # Best-effort file cleanup: a leftover file must never fail the request.
    for doc_id in doc_ids:
        for folder in (config.PAGE_DIR, config.ELA_DIR):
            target = folder / str(doc_id)
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
        (config.MOCK_OCR_DIR / f"doc_{doc_id}.json").unlink(missing_ok=True)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    audit(
        db,
        "APP_DELETE",
        actor=user.username,
        role=user.role,
        entity_type="application",
        entity_id=app_id,
        detail=snapshot,
    )
    return {"deleted": True, "app_id": app_id, **snapshot}


# --------------------------------------------------------------------- list
@router.get("/applications", response_model=list[ApplicationSummary])
def list_applications(
    status: str = "",
    category: str = "",
    q: str = "",
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    if category:
        query = query.filter(Application.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Application.institution_name.ilike(like),
                Application.ref_no.ilike(like),
                Application.aicte_id.ilike(like),
            )
        )
    apps = query.order_by(Application.risk_score.desc(), Application.id.desc()).limit(
        limit
    ).all()
    return [_summary(db, a) for a in apps]


@router.get("/applications/{app_id}", response_model=ApplicationDetail)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    detail = ApplicationDetail.model_validate(app)
    detail.open_flags = sum(1 for f in app.flags if f.status == "OPEN")
    detail.doc_count = len(app.documents)
    detail.reviews = [
        {
            "id": r.id,
            "flag_id": r.flag_id,
            "reviewer_name": r.reviewer_name,
            "decision": r.decision,
            "comment": r.comment,
            "created_at": r.created_at.isoformat(),
        }
        for r in sorted(app.reviews, key=lambda r: r.created_at)
    ]
    return detail


@router.get("/applications/{app_id}/flags", response_model=list[FlagOut])
def list_flags(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app.flags


# ------------------------------------------------------------- media access
@router.get("/applications/{app_id}/documents/{doc_id}/pages/{page}.png")
def get_page_image(
    app_id: int,
    doc_id: int,
    page: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = _get_doc(db, app_id, doc_id)
    png = render.page_png(doc.id, page)
    if png is None:
        render.render_document(doc.stored_path, doc.mime, doc.id)
        png = render.page_png(doc.id, page)
    if png is None:
        raise HTTPException(404, "Page not found")
    return FileResponse(png, media_type="image/png")


@router.get("/applications/{app_id}/documents/{doc_id}/ela.png")
def get_ela_image(
    app_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_doc(db, app_id, doc_id)
    png = config.ELA_DIR / str(doc_id) / "page_1.png"
    if not png.exists():
        raise HTTPException(404, "ELA heatmap not available (validate first)")
    return FileResponse(png, media_type="image/png")


def _get_doc(db: Session, app_id: int, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.application_id != app_id:
        raise HTTPException(404, "Document not found")
    return doc


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Application.status, func.count(Application.id)).group_by(
        Application.status
    ).all()
    counts = {status: n for status, n in rows}
    total = sum(counts.values())
    verified = counts.get("VERIFIED", 0)
    decided = verified + counts.get("INSUFFICIENT_EVIDENCE", 0)
    by_cat = dict(
        db.query(Application.category, func.count(Application.id))
        .group_by(Application.category)
        .all()
    )
    return {
        "total": total,
        "verified": verified,
        "insufficient_evidence": counts.get("INSUFFICIENT_EVIDENCE", 0),
        "in_review": counts.get("IN_REVIEW", 0),
        "approved": counts.get("APPROVED", 0),
        "rejected": counts.get("REJECTED", 0),
        "processing": counts.get("PROCESSING", 0),
        "uploaded": counts.get("UPLOADED", 0),
        "gate_pass_rate": round(verified / decided, 3) if decided else 0.0,
        "by_category": by_cat,
        "mock_mode": config.MOCK_MODE,
    }


@router.get("/config")
def get_config(user: User = Depends(get_current_user)):
    return {
        "mock_mode": config.MOCK_MODE,
        "ocr_confidence_threshold": config.OCR_CONFIDENCE_THRESHOLD,
        "tamper_score_threshold": config.TAMPER_SCORE_THRESHOLD,
        "consistency_threshold": config.CONSISTENCY_THRESHOLD,
        "categories": CATEGORIES,
    }


# ------------------------------------------------------------------ helpers
def _summary(db: Session, app: Application) -> ApplicationSummary:
    s = ApplicationSummary.model_validate(app)
    s.open_flags = (
        db.query(func.count(Flag.id))
        .filter(Flag.application_id == app.id, Flag.status == "OPEN")
        .scalar()
        or 0
    )
    s.doc_count = (
        db.query(func.count(Document.id))
        .filter(Document.application_id == app.id)
        .scalar()
        or 0
    )
    return s
