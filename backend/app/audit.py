"""Append-only audit log helper. Every meaningful action in VeriGate lands here."""

from typing import Any, Optional

from sqlalchemy.orm import Session

from .models import AuditLog, User


def audit(
    db: Session,
    action: str,
    actor: str = "system",
    role: str = "system",
    entity_type: str = "",
    entity_id: Optional[int] = None,
    detail: Optional[dict[str, Any]] = None,
    actor_name: Optional[str] = None,
) -> AuditLog:
    payload = dict(detail or {})
    if actor_name is None and actor not in ("", "system", "seed"):
        # Resolve the human name for a login id so the trail reads like a
        # person, not a username. Append-only safe: enriches the row we are
        # about to insert, never an existing one.
        user = db.query(User).filter(User.username == actor).first()
        if user:
            actor_name = user.full_name
    if actor_name:
        payload["actor_name"] = actor_name
    entry = AuditLog(
        actor=actor,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=payload,
    )
    db.add(entry)
    db.commit()
    return entry
