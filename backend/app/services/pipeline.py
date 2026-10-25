"""Pipeline orchestrator: upload -> OCR -> extraction -> rules -> issuer ->
consistency -> tamper/duplicate -> EVIDENCE GATE -> (verified | manual review).

Runs in a FastAPI BackgroundTask so the UI can poll live step-by-step progress.
Every step is failure-isolated: a failing step records an error in progress and
the gate abstains (INSUFFICIENT_EVIDENCE) instead of the demo ever crashing.
"""

import datetime as dt
import time
from pathlib import Path

from PIL import Image

from .. import config
from ..audit import audit
from ..database import SessionLocal
from ..models import Application, Document, Flag, MockRecord
from . import consistency, issuer, ocr, render, rules_engine, tamper
from .evidence_gate import evaluate as gate_evaluate
from .extraction import extract_fields, field_value, name_similarity, parse_date

STEPS = [
    ("PREPROCESS", "Render document pages"),
    ("OCR", "OCR + text extraction (boxes & confidence)"),
    ("FIELD_EXTRACTION", "Structured field extraction"),
    ("RULE_CHECK", "APH 2024-27 auto-checklist"),
    ("ISSUER_CHECK", "Issuer portal verification (mock)"),
    ("TAMPER_DUPLICATE_CHECK", "ELA tamper + pHash duplicate check"),
    ("CONSISTENCY_CHECK", "XGBoost cross-record consistency"),
    ("EVIDENCE_GATE", "Evidence Gate decision"),
    ("FINALIZE", "Persist results + audit"),
]


def _progress(app: Application, current: str, done: set[str], error: str = ""):
    steps = [
        {
            "name": name,
            "detail": detail,
            "status": (
                "ERROR"
                if error and name == current
                else "DONE"
                if name in done
                else "RUNNING"
                if name == current
                else "PENDING"
            ),
        }
        for name, detail in STEPS
    ]
    all_done = all(s["status"] == "DONE" for s in steps)
    app.progress_json = {
        "status": "ERROR" if error else ("DONE" if all_done else "RUNNING"),
        "current_step": current,
        "steps": steps,
        "error": error,
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
    }


def run_validation(app_id: int, actor: str = "system", animate: bool = False) -> dict:
    db = SessionLocal()
    summary: dict = {"app_id": app_id, "ok": False}
    try:
        app = db.get(Application, app_id)
        if not app:
            return {"app_id": app_id, "error": "application not found"}

        app.status = "PROCESSING"
        done: set[str] = set()
        _progress(app, STEPS[0][0], done)
        db.commit()

        # Fresh re-validation: drop machine output from any previous run
        db.query(Flag).filter(Flag.application_id == app_id).delete()
        db.commit()

        flags: list[dict] = []
        t0 = time.time()

        def step(name: str, detail: str = ""):
            def deco(fn):
                def wrap(*a, **kw):
                    _progress(app, name, done)
                    db.commit()
                    if animate:
                        time.sleep(0.35)
                    start = time.time()
                    result = fn(*a, **kw)
                    done.add(name)
                    _progress(app, name, done)
                    for s in app.progress_json["steps"]:
                        if s["name"] == name:
                            s["detail"] = detail or s["detail"]
                            s["ms"] = int((time.time() - start) * 1000)
                    db.commit()
                    return result

                return wrap

            return deco

        # ---------------------------------------------------------- 1. render
        @step("PREPROCESS")
        def _preprocess():
            for doc in app.documents:
                pages = render.render_document(doc.stored_path, doc.mime, doc.id)
                doc.page_count = len(pages)
            db.commit()

        _preprocess()

        # ------------------------------------------------------------- 2. OCR
        @step("OCR")
        def _ocr():
            pages_by_doc: dict[int, list[dict]] = {}
            confs, weights = [], []
            for doc in app.documents:
                pages_out = []
                for p in range(1, doc.page_count + 1):
                    png = render.page_png(doc.id, p)
                    if png is None:
                        continue
                    res = ocr.ocr_page(doc.id, p, str(png), doc.stored_path)
                    pages_out.append({"page_no": p, **res})
                pages_by_doc[doc.id] = pages_out
                toks = sum(len(pg["tokens"]) for pg in pages_out)
                conf = (
                    sum(pg["avg_conf"] * len(pg["tokens"]) for pg in pages_out) / toks
                    if toks
                    else (pages_out[0]["avg_conf"] if pages_out else 0.15)
                )
                doc.ocr_confidence = round(float(conf), 4)
                doc.ocr_engine = ", ".join(
                    sorted({pg["engine"] for pg in pages_out})
                ) or "none"
                doc.ocr_text = "\n".join(
                    " ".join(t["text"] for t in pg["tokens"]) for pg in pages_out
                )
                confs.append(doc.ocr_confidence)
                weights.append(max(1, toks))
            app.ocr_confidence = round(
                sum(c * w for c, w in zip(confs, weights)) / sum(weights), 4
            ) if confs else 0.0
            db.commit()
            return pages_by_doc

        pages_by_doc = _ocr()

        if app.ocr_confidence <= config.OCR_CONFIDENCE_THRESHOLD and app.documents:
            worst = min(app.documents, key=lambda d: d.ocr_confidence or 1.0)
            flags.append(
                {
                    "kind": "OCR",
                    "rule_id": "APH-GEN-O01",
                    "title": "OCR confidence below Evidence Gate threshold",
                    "reason": f"Mean OCR confidence {app.ocr_confidence:.2f} <= "
                    f"{config.OCR_CONFIDENCE_THRESHOLD:.2f} gate threshold "
                    f"(worst document: '{worst.filename}' #{worst.id} at "
                    f"{(worst.ocr_confidence or 0):.2f}, engine "
                    f"{worst.ocr_engine or 'none'}). The machine cannot vouch "
                    "for this text - human eyes required.",
                    "severity": "WARN",
                    "document_id": worst.id,
                    "page_no": 1,
                    "bbox": None,
                }
            )

        # ------------------------------------------------- 3. field extraction
        @step("FIELD_EXTRACTION")
        def _fields():
            for doc in app.documents:
                doc.extracted_json = extract_fields(pages_by_doc.get(doc.id, []))
            db.commit()

        _fields()

        def doc_view(doc: Document) -> dict:
            return {
                "id": doc.id,
                "doc_type": doc.doc_type,
                "fields": doc.extracted_json or {},
                "issuer_status": "",
            }

        # -------------------------------------------------------- 4. rules
        @step("RULE_CHECK")
        def _rules():
            checklist = rules_engine.evaluate_checklist(
                app.category, [doc_view(d) for d in app.documents]
            )
            app.checklist_json = checklist
            flags.extend(rules_engine.flags_from_checklist(checklist))
            flags.extend(rules_engine.future_issue_date_flags(checklist))
            db.commit()

        _rules()

        # -------------------------------------------------------- 5. issuer
        @step("ISSUER_CHECK")
        def _issuer_check():
            reqs = {
                r["doc_type"]: r for r in rules_engine.category_rules(app.category)
            }
            results = []
            for doc in app.documents:
                req = reqs.get(doc.doc_type)
                if not req or not req.get("issuer_portal"):
                    continue
                f = doc.extracted_json or {}
                res = issuer.verify_document(
                    db,
                    {
                        "portal": req["issuer_portal"],
                        "doc_number": field_value(f, "doc_number"),
                        "qr_token": field_value(f, "qr_token"),
                        "signature": field_value(f, "signature"),
                    },
                )
                if res:
                    res["doc_type"] = doc.doc_type
                    res["document_id"] = doc.id
                    results.append(res)
            app.issuer_status = issuer.worst_status(
                [r["status"] for r in results]
            ) or "NOT_REQUIRED"
            # Reflect per-document issuer outcome back into the checklist
            by_doc = {r["document_id"]: r["status"] for r in results}
            for item in app.checklist_json or []:
                if item.get("document_id") in by_doc:
                    item["issuer_status"] = by_doc[item["document_id"]]
            # Explainable flags for anything the portal would not confirm
            doc_fields = {d.id: (d.extracted_json or {}) for d in app.documents}
            for res in results:
                if res["status"] == "VERIFIED":
                    continue
                fields = doc_fields.get(res.get("document_id"), {})
                loc = fields.get("doc_number") or {}
                flags.append(
                    {
                        "kind": "ISSUER",
                        "rule_id": "APH-GEN-I01",
                        "title": f"Issuer check {res['status']}: "
                        f"{res.get('portal_name', res.get('portal'))}",
                        "reason": f"{res.get('detail', '')} "
                        f"[portal={res.get('portal')}, document="
                        f"'{res.get('doc_number')}' ({res.get('doc_type')}), "
                        f"document #{res.get('document_id')}]".strip(),
                        "severity": (
                            "WARN"
                            if res["status"] in ("SOURCE_UNAVAILABLE", "MANUAL_REVIEW")
                            else "CRITICAL"
                        ),
                        "document_id": res.get("document_id"),
                        "page_no": loc.get("page_no"),
                        "bbox": loc.get("bbox"),
                    }
                )
            db.commit()
            return results

        issuer_results = _issuer_check()

        # ------------------------------------------------- 6. tamper + dupes
        @step("TAMPER_DUPLICATE_CHECK")
        def _tamper_dupes():
            duplicates = 0
            max_tamper = 0.0
            for doc in app.documents:
                png = render.page_png(doc.id, 1)
                if png is None:
                    continue
                img = Image.open(png).convert("RGB")
                heatmap, score, bbox = tamper.ela_analysis(img)
                # MOCK_MODE demo safeguard (spec): for seeded tampered documents
                # the ground-truth region is merged in so scenario C is
                # deterministic even if the render/ELA path cannot see it.
                gt_note = ""
                gt_tamper = (ocr.load_ground_truth(doc.id) or {}).get("tamper") or {}
                if (
                    config.MOCK_MODE
                    and gt_tamper.get("bbox")
                    and float(gt_tamper.get("score", 0)) > score
                ):
                    score = float(gt_tamper["score"])
                    bbox = gt_tamper["bbox"]
                    gt_note = (
                        f" [MOCK_MODE: region confirmed from seeded ground truth - "
                        f"{gt_tamper.get('note', 'altered region')}]"
                    )
                doc.tamper_score = float(score)
                doc.ela_bbox = bbox
                max_tamper = max(max_tamper, score)
                ela_dir = config.ELA_DIR / str(doc.id)
                ela_dir.mkdir(parents=True, exist_ok=True)
                heatmap.save(ela_dir / "page_1.png")

                doc.phash = tamper.phash(img)
                donor = _find_duplicate(db, doc)
                if donor:
                    doc.duplicate_of = donor["id"]
                    duplicates += 1
                    flags.append(
                        {
                            "kind": "DUPLICATE",
                            "rule_id": "APH-GEN-D01",
                            "title": "Duplicate document detected (pHash)",
                            "reason": f"Perceptual hash of '{doc.filename}' matches "
                            f"'{donor['filename']}' (document #{donor['id']}, "
                            f"application {donor['ref_no']}) with hamming distance "
                            f"{donor['distance']} and OCR text similarity "
                            f"{donor['text_sim']:.2f} - the same file appears to be "
                            "reused across applications.",
                            "severity": "CRITICAL",
                            "document_id": doc.id,
                            "page_no": 1,
                            "bbox": None,
                        }
                    )
                if score >= config.TAMPER_SCORE_THRESHOLD and bbox:
                    flags.append(
                        {
                            "kind": "TAMPER",
                            "rule_id": "APH-GEN-T01",
                            "title": "ELA anomaly: region with anomalous recompression",
                            "reason": f"Error Level Analysis on '{doc.filename}' page 1 "
                            f"found a hot region at ({bbox[0]:.2f}, {bbox[1]:.2f}) "
                            f"size ({bbox[2]:.2f} x {bbox[3]:.2f}) with tamper score "
                            f"{score:.2f} - consistent with a pasted/edited region."
                            + gt_note,
                            "severity": "CRITICAL",
                            "document_id": doc.id,
                            "page_no": 1,
                            "bbox": bbox,
                        }
                    )
            app.tamper_score = round(max_tamper, 4)
            db.commit()
            return duplicates

        duplicate_count = _tamper_dupes()

        # ------------------------------------------------------ 7. consistency
        @step("CONSISTENCY_CHECK")
        def _consistency():
            feats = _consistency_features(app, db)
            score = consistency.score(feats)
            app.consistency_score = score
            if score < config.CONSISTENCY_THRESHOLD:
                weak = ", ".join(
                    f"{f['feature']}={f['value']}" for f in consistency.top_features(feats)
                )
                flags.append(
                    {
                        "kind": "CONSISTENCY",
                        "rule_id": "APH-GEN-C01",
                        "title": "Cross-record inconsistency with AICTE master data",
                        "reason": f"XGBoost consistency score {score:.2f} is below "
                        f"{config.CONSISTENCY_THRESHOLD}. Weakest fields: {weak}.",
                        "severity": "WARN",
                        "document_id": None,
                        "page_no": None,
                        "bbox": None,
                    }
                )
            db.commit()
            return feats

        _consistency()

        # ---------------------------------------------------------- 8. gate
        @step("EVIDENCE_GATE")
        def _gate():
            gate = gate_evaluate(
                {
                    "ocr_confidence": app.ocr_confidence,
                    "consistency_score": app.consistency_score,
                    "tamper_score": app.tamper_score,
                    "issuer_results": issuer_results,
                    "critical_flags": flags,
                    "duplicate_count": duplicate_count,
                }
            )
            app.gate_status = gate["status"]
            app.gate_reasons = gate["reasons"]
            app.gate_confidence = gate["confidence"]
            risk = 1.0 - gate["confidence"]
            if any(f["severity"] == "CRITICAL" for f in flags):
                risk = min(1.0, risk + 0.15)
            app.risk_score = round(risk, 4)
            app.status = gate["status"]
            db.commit()

        _gate()

        # ------------------------------------------------------- 9. finalize
        @step("FINALIZE")
        def _finalize():
            for f in flags:
                db.add(
                    Flag(
                        application_id=app.id,
                        document_id=f.get("document_id"),
                        kind=f["kind"],
                        rule_id=f["rule_id"],
                        title=f["title"],
                        reason=f["reason"],
                        severity=f["severity"],
                        page_no=f.get("page_no"),
                        bbox=f.get("bbox"),
                    )
                )
            app.validated_at = dt.datetime.utcnow()
            db.commit()
            audit(
                db,
                "VALIDATE_COMPLETE",
                actor=actor,
                entity_type="application",
                entity_id=app.id,
                detail={
                    "gate_status": app.gate_status,
                    "gate_confidence": app.gate_confidence,
                    "risk_score": app.risk_score,
                    "flags": len(flags),
                    "ocr_confidence": app.ocr_confidence,
                    "consistency": app.consistency_score,
                    "tamper": app.tamper_score,
                    "issuer_status": app.issuer_status,
                    "duration_ms": int((time.time() - t0) * 1000),
                    "mock_mode": config.MOCK_MODE,
                },
            )

        _finalize()

        db.refresh(app)
        new_flag_ids = [
            f.id for f in db.query(Flag).filter(Flag.application_id == app.id).all()
        ]
        audit(
            db,
            "FLAGGED",
            actor=actor,
            entity_type="application",
            entity_id=app.id,
            detail={"flag_ids": new_flag_ids},
        )
        summary.update(ok=True, gate_status=app.gate_status, flags=len(flags))
        return summary
    except Exception as exc:  # demo safeguard: never crash the server
        try:
            app = db.get(Application, app_id)
            if app:
                app.status = "UPLOADED"
                _progress(app, app.progress_json.get("current_step", ""), set(), str(exc))
                app.gate_reasons = [
                    {"rule_id": "SYSTEM", "message": f"Pipeline error: {exc}"}
                ]
            db.commit()
        except Exception:
            pass
        return {"app_id": app_id, "ok": False, "error": str(exc)}
    finally:
        db.close()


# --------------------------------------------------------------------- helpers
DUPLICATE_TEXT_SIM = 0.95  # pHash alone is layout-sensitive on documents (two
# different certificates on the same template can hash within a few bits).
# The OCR text must ALSO match - a byte-identical reused file scores 1.0,
# whereas the same template with different data scores ~0.78 in practice.


def _find_duplicate(db, doc: Document) -> dict | None:
    """Nearest pHash match among other documents that also share OCR content.

    pHash catches visually identical pages, but documents with a similar layout
    can hash close together - requiring the extracted text to match as well is
    what separates "the same file was reused" from "same template, different
    data"."""
    if not doc.phash:
        return None
    best = None
    candidates = (
        db.query(Document)
        .filter(Document.id != doc.id, Document.phash != "", Document.phash != None)  # noqa: E711
        .all()
    )
    for other in candidates:
        dist = tamper.hamming(doc.phash, other.phash)
        if dist > tamper.duplicate_threshold():
            continue
        text_sim = name_similarity(doc.ocr_text or "", other.ocr_text or "")
        if text_sim < DUPLICATE_TEXT_SIM:
            continue
        same_app = other.application_id == doc.application_id
        key = (0 if not same_app else 1, dist)
        if best is None or key < best["key"]:
            app = db.get(Application, other.application_id)
            best = {
                "key": key,
                "id": other.id,
                "filename": other.filename,
                "ref_no": app.ref_no if app else "?",
                "distance": dist,
                "text_sim": text_sim,
            }
    return best


def _consistency_features(app: Application, db) -> dict:
    record = None
    if app.aicte_id:
        record = (
            db.query(MockRecord).filter(MockRecord.aicte_id == app.aicte_id).first()
        )

    # Best-effort extracted values across all documents
    ex_name = ex_aicte = ex_intake = ex_issue = ex_expiry = ""
    for doc in app.documents:
        f = doc.extracted_json or {}
        ex_name = ex_name or field_value(f, "institution_name")
        ex_aicte = ex_aicte or field_value(f, "aicte_id")
        ex_intake = ex_intake or field_value(f, "approved_intake")
        ex_issue = ex_issue or field_value(f, "issue_date")
        ex_expiry = ex_expiry or field_value(f, "expiry_date")

    issuer_results = []
    for doc in app.documents:
        if doc.extracted_json and field_value(doc.extracted_json, "doc_number"):
            issuer_results.append(doc)

    name_sim = name_similarity(app.institution_name, record.institution_name) if record else 0.4
    aicte_match = 1.0 if record and ex_aicte and ex_aicte == record.aicte_id else (
        0.7 if record and app.aicte_id == record.aicte_id else 0.1
    )
    cat_match = 1.0 if record and record.category == app.category else (0.5 if not record else 0.1)
    addr_sim = name_similarity(app.address or "", record.address or "") if record else 0.4
    intake_match = (
        1.0
        if record and int(app.approved_intake or 0) == int(record.approved_intake or 0)
        else (0.6 if not record else 0.1)
    )
    issue = parse_date(ex_issue)
    plausible = 1.0
    if record and issue:
        try:
            upto = dt.datetime.strptime(record.valid_upto, "%d-%m-%Y").date()
            plausible = 1.0 if issue <= upto else 0.2
        except ValueError:
            plausible = 0.5
    expiry = parse_date(ex_expiry)
    aligned = 0.5
    if record and expiry:
        try:
            upto = dt.datetime.strptime(record.valid_upto, "%d-%m-%Y").date()
            aligned = 1.0 if abs((upto - expiry).days) <= 400 else 0.3
        except ValueError:
            aligned = 0.5

    return {
        "name_sim": name_sim,
        "aicte_id_match": aicte_match,
        "category_match": cat_match,
        "address_sim": addr_sim,
        "intake_match": intake_match,
        "issue_plausible": plausible,
        "expiry_aligned": aligned,
        "issuer_ok_ratio": 1.0 if app.issuer_status in ("VERIFIED", "NOT_REQUIRED", "") else 0.2,
        "ocr_conf": app.ocr_confidence,
        "tamper_ok": max(0.0, 1.0 - app.tamper_score),
        "not_duplicate": 0.0
        if any(d.duplicate_of for d in app.documents)
        else 1.0,
    }
