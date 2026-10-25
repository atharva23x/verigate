"""Audit log: filterable, exportable to CSV. Append-only by design."""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..security import get_current_user

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("")
def list_audit_log(
    actor: str = "",
    action: str = "",
    entity_type: str = "",
    entity_id: int = 0,
    date_from: str = "",
    date_to: str = "",
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(AuditLog)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.filter(AuditLog.ts >= date_from)
    if date_to:
        q = q.filter(AuditLog.ts <= date_to + " 23:59:59")
    total = q.count()
    entries = q.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": e.id,
                "ts": e.ts.isoformat() + "Z",
                "actor": e.actor,
                "role": e.role,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "detail": e.detail,
            }
            for e in entries
        ],
    }


@router.get("/actions")
def list_actions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()
    return [a for a, _ in rows]


@router.get("/export")
def export_csv(
    actor: str = "",
    action: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(AuditLog)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if action:
        q = q.filter(AuditLog.action == action)
    entries = q.order_by(AuditLog.id.asc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "timestamp_utc", "actor", "role", "action", "entity_type", "entity_id", "detail_json"]
    )
    import json

    for e in entries:
        writer.writerow(
            [
                e.id,
                e.ts.isoformat() + "Z",
                e.actor,
                e.role,
                e.action,
                e.entity_type,
                e.entity_id,
                json.dumps(e.detail, ensure_ascii=False),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=verigate-audit-{len(entries)}.csv"
        },
    )
