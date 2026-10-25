"""Issuer verification client.

MOCK_MODE=True  -> calls the mock portals in-process (instant, never crashes).
MOCK_MODE=False -> POSTs to http://localhost:8000/mock-issuer/{portal}/verify
                   like a real integration would, and falls back to in-process
                   if the HTTP call fails.

Statuses: VERIFIED | INVALID | EXPIRED | NOT_FOUND | SOURCE_UNAVAILABLE | MANUAL_REVIEW
"""

from typing import Optional

from sqlalchemy.orm import Session

from .. import config
from ..mock_issuer_api import verify as mock_verify

WORST_ORDER = [
    "VERIFIED",
    "MANUAL_REVIEW",
    "SOURCE_UNAVAILABLE",
    "EXPIRED",
    "NOT_FOUND",
    "INVALID",
]


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return ""
    return max(statuses, key=lambda s: WORST_ORDER.index(s) if s in WORST_ORDER else 0)


def verify_document(db: Session, doc: dict) -> Optional[dict]:
    """doc: {portal, doc_number, qr_token, signature}. Returns a verify() payload."""
    portal = doc.get("portal")
    if not portal:
        return None
    args = dict(
        portal=portal,
        doc_number=doc.get("doc_number", ""),
        qr_token=doc.get("qr_token", ""),
        signature=doc.get("signature", ""),
    )
    if config.MOCK_MODE:
        return mock_verify(db, **args)

    # HTTP path (real-integration simulation), with in-process fallback
    try:
        import httpx

        url = f"http://localhost:8000/mock-issuer/{portal}/verify"
        r = httpx.post(
            url,
            json={
                "doc_number": args["doc_number"],
                "qr_token": args["qr_token"],
                "signature": args["signature"],
            },
            timeout=2.5,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        result = mock_verify(db, **args)
        result["detail"] = (
            f"[HTTP call to issuer portal failed: {exc}; verified in-process] "
            + str(result.get("detail", ""))
        )
        return result
