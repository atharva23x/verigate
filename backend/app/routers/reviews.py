"""Manual review queue + decision endpoints.

The Evidence Gate abstains; humans decide. Every decision is recorded in the
append-only audit log.
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import audit
from ..database import get_db
from ..models import Application, Flag, ReviewDecision, User
from ..schemas import DecisionOut, DecisionRequest
from ..security import require_roles

router = APIRouter(tags=["reviews"])

DECISIONS = ("APPROVE", "REJECT", "REQUEST_INFO")


@router.get("/reviews/queue")
def review_queue(db: Session = Depends(get_db), user: User = Depends(require_roles("officer", "reviewer", "auditor"))):
    """Applications sitting in the manual review queue (risk-ranked)."""
    apps = (
        db.query(Application)
        .filter(Application.status.in_(["INSUFFICIENT_EVIDENCE", "IN_REVIEW"]))
        .order_by(Application.risk_score.desc())
        .all()
    )
    queue = []
    for app in apps:
        open_flags = [f for f in app.flags if f.status == "OPEN"]
        if not open_flags and app.status != "IN_REVIEW":
            continue
        queue.append(
            {
                "application": {
                    "id": app.id,
                    "ref_no": app.ref_no,
                    "institution_name": app.institution_name,
                    "category": app.category,
                    "status": app.status,
                    "risk_score": app.risk_score,
                    "gate_confidence": app.gate_confidence,
                    "issuer_status": app.issuer_status,
                    "gate_reasons": app.gate_reasons,
                },
                "open_flags": [
                    {
                        "id": f.id,
                        "title": f.title,
                        "rule_id": f.rule_id,
                        "severity": f.severity,
                        "kind": f.kind,
                        "has_location": bool(f.bbox),
                    }
                    for f in open_flags
                ],
                "decided_flags": db.query(func.count(ReviewDecision.id))
                .filter(ReviewDecision.application_id == app.id)
                .scalar()
                or 0,
            }
        )
    return queue


@router.post("/reviews/{flag_id}/decision", response_model=DecisionOut)
def decide(
    flag_id: int,
    body: DecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("officer", "reviewer")),
):
    if body.decision not in DECISIONS:
        raise HTTPException(400, f"decision must be one of {DECISIONS}")
    flag = db.get(Flag, flag_id)
    if not flag:
        raise HTTPException(404, "Flag not found")
    app = db.get(Application, flag.application_id)
    if not app:
        raise HTTPException(404, "Application not found")

    decision = ReviewDecision(
        flag_id=flag.id,
        application_id=app.id,
        reviewer_id=user.id,
        reviewer_name=user.full_name,
        decision=body.decision,
        comment=body.comment.strip(),
    )
    db.add(decision)
    if body.decision in ("APPROVE", "REJECT"):
        flag.status = "RESOLVED"

    # Roll the application status up from its flags
    open_left = any(f.status == "OPEN" for f in app.flags if f.id != flag.id)
    if body.decision == "REQUEST_INFO" or open_left:
        app.status = "IN_REVIEW"
    else:
        all_decisions = [d.decision for d in app.reviews] + [body.decision]
        if "REJECT" in all_decisions:
            app.status = "REJECTED"
        elif "REQUEST_INFO" in all_decisions:
            app.status = "IN_REVIEW"
        else:
            app.status = "APPROVED"
    db.commit()

    audit(
        db,
        "REVIEW_DECISION",
        actor=user.username,
        role=user.role,
        entity_type="flag",
        entity_id=flag.id,
        detail={
            "application_id": app.id,
            "decision": body.decision,
            "comment": body.comment,
            "flag_rule": flag.rule_id,
            "app_status": app.status,
        },
    )
    return decision
