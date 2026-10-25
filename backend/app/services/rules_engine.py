"""Rule engine: APH 2024-27 auto-checklist per institution category.

Evaluates rules.json against the uploaded documents + extracted fields and
produces (a) the checklist shown in the UI and (b) explainable flags.
"""

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

from .extraction import field_value, parse_date

_RULES_PATH = Path(__file__).resolve().parent.parent / "rules.json"


def _today() -> dt.date:
    return dt.datetime.utcnow().date()


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


def category_rules(category: str) -> list[dict]:
    return load_rules()["categories"].get(category, {}).get("mandatory_documents", [])


def evaluate_checklist(category: str, documents: list[dict]) -> list[dict]:
    """documents: [{id, doc_type, fields:{...}, issuer_status}] -> checklist items."""
    checklist: list[dict] = []
    by_type: dict[str, dict] = {}
    for doc in documents:
        # First upload of a given type satisfies the slot
        by_type.setdefault(doc["doc_type"], doc)

    for req in category_rules(category):
        present = by_type.get(req["doc_type"])
        item = {
            "rule_id": req["rule_id"],
            "doc_type": req["doc_type"],
            "name": req["name"],
            "required": True,
            "issuer_portal": req.get("issuer_portal"),
            "validity_required": req.get("validity_required", False),
            "present": bool(present),
            "document_id": present["id"] if present else None,
            "status": "OK",
            "issuer_status": (present or {}).get("issuer_status", ""),
            "fields": {},
        }
        if present:
            fields = present.get("fields", {}) or {}
            missing_fields = []
            for fname in req.get("required_fields", []):
                f = fields.get(fname) or {}
                ok = bool(f.get("value"))
                item["fields"][fname] = {
                    "ok": ok,
                    "value": f.get("value", ""),
                    "confidence": f.get("confidence", 0.0),
                    "page_no": f.get("page_no"),
                    "bbox": f.get("bbox"),
                }
                if not ok:
                    missing_fields.append(fname)
            if missing_fields:
                item["status"] = "WARN"
                item["missing_fields"] = missing_fields
            if req.get("validity_required"):
                expiry = parse_date(field_value(fields, "expiry_date"))
                if expiry and expiry < _today():
                    item["status"] = "EXPIRED"
                    item["expiry_date"] = expiry.strftime("%d-%m-%Y")
        else:
            item["status"] = "MISSING"
        checklist.append(item)
    return checklist


def flags_from_checklist(checklist: list[dict]) -> list[dict]:
    """Turn checklist problems into explainable flags."""
    flags: list[dict] = []
    for item in checklist:
        if item["status"] == "MISSING":
            flags.append(
                {
                    "kind": "RULE",
                    "rule_id": item["rule_id"],
                    "title": f"Missing mandatory document: {item['name']}",
                    "reason": f"Rule {item['rule_id']} (APH 2024-27): '{item['name']}' "
                    f"is mandatory for this category but was not uploaded.",
                    "severity": "CRITICAL",
                    "document_id": None,
                    "page_no": None,
                    "bbox": None,
                }
            )
        elif item["status"] == "EXPIRED":
            expiry_field = item["fields"].get("expiry_date", {})
            flags.append(
                {
                    "kind": "RULE",
                    "rule_id": "APH-GEN-F02",
                    "title": f"Expired document: {item['name']}",
                    "reason": f"Rule APH-GEN-F02: expiry date {item.get('expiry_date')} "
                    f"is in the past (doc_type {item['doc_type']}, "
                    f"document #{item['document_id']}).",
                    "severity": "CRITICAL",
                    "document_id": item.get("document_id"),
                    "page_no": expiry_field.get("page_no"),
                    "bbox": expiry_field.get("bbox"),
                }
            )
        elif item.get("missing_fields"):
            fname = item["missing_fields"][0]
            field = item["fields"].get(fname, {})
            flags.append(
                {
                    "kind": "EXTRACTION",
                    "rule_id": "APH-GEN-F03",
                    "title": f"Field '{fname}' not found in {item['name']}",
                    "reason": f"Rule APH-GEN-F03: mandatory field '{fname}' could not be "
                    f"located in document #{item.get('document_id')} "
                    f"(doc_type {item['doc_type']}).",
                    "severity": "WARN",
                    "document_id": item.get("document_id"),
                    "page_no": field.get("page_no"),
                    "bbox": field.get("bbox"),
                }
            )
    return flags


def future_issue_date_flags(checklist: list[dict]) -> list[dict]:
    flags = []
    for item in checklist:
        f = item.get("fields", {}).get("issue_date", {})
        d = parse_date(f.get("value"))
        if d and d > _today():
            flags.append(
                {
                    "kind": "RULE",
                    "rule_id": "APH-GEN-F01",
                    "title": f"Future issue date in {item['name']}",
                    "reason": f"Rule APH-GEN-F01: issue date {f.get('value')} is after today.",
                    "severity": "CRITICAL",
                    "document_id": item.get("document_id"),
                    "page_no": f.get("page_no"),
                    "bbox": f.get("bbox"),
                }
            )
    return flags
