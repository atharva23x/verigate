"""Mock issuer verification portals.

Simulates the UGC / AICTE / State board / Fire dept / Pharmacy council portals
that an EoA officer would cross-check documents against. Two ways to use it:

  1. In-process (default, MOCK_MODE=True):  issuer.verify(...)  -> instant
  2. Over HTTP (demo of a "real" integration):
        POST http://localhost:8000/mock-issuer/{portal}/verify
     The issuer service falls back to in-process if the HTTP call fails.

Statuses: VERIFIED | INVALID | EXPIRED | NOT_FOUND | SOURCE_UNAVAILABLE | MANUAL_REVIEW

Portals can be toggled DOWN at runtime (demo scenario D - the pipeline must
report SOURCE_UNAVAILABLE and keep going, never crash, never guess).
"""

import datetime as dt
import hashlib
import hmac
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import IssuerRecord

HMAC_SECRET = "verigate-mock-issuer-secret"
PORTALS = {
    "aicte_portal": "AICTE Approval Portal",
    "state_board": "State Technical Board / University Portal",
    "fire_dept": "State Fire & Emergency Services Portal",
    "pharmacy_council": "Pharmacy Council of India Portal",
    "ugc": "UGC University Grants Commission Portal",
}

# Portals simulated as DOWN at runtime (demo control via API). Outages can also
# be pinned to a single record via IssuerRecord.source_unavailable (restart-safe).
# NOTE: a global outage on a shared portal would fail every application - the
# seeded demo scenario D pins the outage to one specific record instead.
OUTAGE: set[str] = set(config.ISSUER_OUTAGE_PORTALS)


def signature_for(portal: str, doc_number: str, qr_token: str = "") -> str:
    """The 'digital signature' an authentic portal stamps on an issued document."""
    msg = f"{portal}|{doc_number}|{qr_token}".encode()
    return hmac.new(HMAC_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:48]


def set_outage(portal: str, down: bool) -> None:
    if down:
        OUTAGE.add(portal)
    else:
        OUTAGE.discard(portal)


class VerifyRequest(BaseModel):
    doc_number: str
    qr_token: str = ""
    signature: str = ""


def verify(
    db: Session,
    portal: str,
    doc_number: str,
    qr_token: str = "",
    signature: str = "",
) -> dict[str, Any]:
    """Core verification used by the pipeline (in-process path)."""
    now = dt.datetime.utcnow()
    result: dict[str, Any] = {
        "portal": portal,
        "portal_name": PORTALS.get(portal, portal),
        "doc_number": doc_number,
        "status": "VERIFIED",
        "detail": "",
        "valid_upto": "",
        "checked_at": now.isoformat() + "Z",
    }

    if portal not in PORTALS:
        result.update(status="MANUAL_REVIEW", detail=f"Unknown portal '{portal}'.")
        return result

    if portal in OUTAGE:
        result.update(
            status="SOURCE_UNAVAILABLE",
            detail=f"{PORTALS[portal]} did not respond (simulated outage). "
            "Document NOT rejected - routed to manual review instead.",
        )
        return result

    rec = (
        db.query(IssuerRecord)
        .filter(IssuerRecord.portal == portal, IssuerRecord.doc_number == doc_number)
        .first()
    )
    if getattr(rec, "source_unavailable", False):
        result.update(
            status="SOURCE_UNAVAILABLE",
            detail=f"{PORTALS[portal]} did not respond (simulated outage for this "
            "record). Document NOT rejected - routed to manual review instead.",
        )
        return result
    if not rec:
        result.update(
            status="NOT_FOUND",
            detail=f"No record of document '{doc_number}' found in {PORTALS[portal]}.",
        )
        return result

    result["valid_upto"] = rec.valid_upto

    if signature and signature.lower() != (rec.signature or "").lower():
        result.update(
            status="INVALID",
            detail="Digital signature does not match the portal's issued copy "
            "(document appears altered or forged).",
        )
        return result

    if qr_token and qr_token != (rec.qr_token or ""):
        result.update(
            status="INVALID",
            detail="QR token on the document does not match the portal record.",
        )
        return result

    try:
        expiry = dt.datetime.strptime(rec.valid_upto, "%d-%m-%Y")
        if expiry < now:
            result.update(
                status="EXPIRED",
                detail=f"Portal record expired on {rec.valid_upto}.",
            )
            return result
    except (ValueError, TypeError):
        pass

    result.update(status="VERIFIED", detail="Portal confirmed the document.")
    return result


# --------------------------------------------------------------------- router
router = APIRouter(prefix="/mock-issuer", tags=["mock-issuer"])


@router.get("/portals")
def list_portals():
    return {
        "portals": [
            {"id": pid, "name": name, "status": "DOWN" if pid in OUTAGE else "UP"}
            for pid, name in PORTALS.items()
        ]
    }


@router.post("/portals/{portal}/outage")
def toggle_outage(
    portal: str,
    down: bool = True,
    doc_number: str = "",
    db: Session = Depends(get_db),
):
    """Global portal outage (down=true), or pinned to a single document record
    when doc_number is given (persistent across restarts)."""
    if portal not in PORTALS:
        raise HTTPException(404, f"Unknown portal '{portal}'")
    if doc_number:
        rec = (
            db.query(IssuerRecord)
            .filter(IssuerRecord.portal == portal, IssuerRecord.doc_number == doc_number)
            .first()
        )
        if not rec:
            raise HTTPException(404, f"No record '{doc_number}' in {portal}")
        rec.source_unavailable = down
        db.commit()
        return {"portal": portal, "doc_number": doc_number,
                "status": "DOWN" if down else "UP", "scope": "record"}
    set_outage(portal, down)
    return {"portal": portal, "status": "DOWN" if down else "UP", "scope": "portal"}


@router.post("/{portal}/verify")
def verify_http(portal: str, body: VerifyRequest, db: Session = Depends(get_db)):
    """The endpoint a 'real' integration would call."""
    return verify(db, portal, body.doc_number, body.qr_token, body.signature)
