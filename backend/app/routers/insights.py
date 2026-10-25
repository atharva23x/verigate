"""Insight endpoints behind VeriGate's five new views.

    GET /applications/{id}/report        -> printable verification PDF (reportlab)
    GET /applications/{id}/consistency   -> submitted values vs AICTE master record
    GET /applications/{id}/duplicates    -> duplicate pair(s), both copies side by side
    GET /issuer/status                   -> mock issuer portal health + check outcomes
    GET /dashboard/analytics             -> portfolio trends (flags, gaps, queue, risk)

All are read-only and open to any authenticated role: officer, reviewer and
auditor see the same evidence - only deciding rights differ. Nothing here can
change an application or a gate verdict.
"""

import datetime as dt
import xml.sax.saxutils as xiu
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import config
from ..audit import audit
from ..database import get_db
from ..mock_issuer_api import OUTAGE, PORTALS, verify as mock_verify
from ..models import (
    Application,
    Document,
    Flag,
    IssuerRecord,
    MockRecord,
    ReviewDecision,
    User,
)
from ..security import get_current_user
from ..services import consistency, tamper
from ..services.extraction import field_value, name_similarity
from ..services.pipeline import _consistency_features

router = APIRouter(tags=["insights"])


# --------------------------------------------------------------------- utils
def _get_app(db: Session, app_id: int) -> Application:
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return app


def _s(value: Any) -> str:
    """Sanitize for reportlab's latin-1 core fonts (never let a stray unicode
    character abort a demo download)."""
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\x00", "")
    return text.encode("latin-1", "replace").decode("latin-1")


# ------------------------------------------------------------- PDF reporting
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        HRFlowable,
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _RL_AVAILABLE = True
except Exception:  # pragma: no cover - reportlab ships with the venv
    _RL_AVAILABLE = False

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
if _RL_AVAILABLE:
    _font_dir = Path(__import__("os").getenv("WINDIR", "C:/Windows")) / "Fonts"
    for _reg, _bold in (
        ("arial.ttf", "arialbd.ttf"),
        ("calibri.ttf", "calibrib.ttf"),
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    ):
        try:
            pdfmetrics.registerFont(TTFont("VG", str(_font_dir / _reg)))
            pdfmetrics.registerFont(TTFont("VGB", str(_font_dir / _bold)))
            FONT, FONT_BOLD = "VG", "VGB"
            break
        except Exception:
            continue

_LOGO = Path(config.BASE_DIR).parent / "frontend" / "public" / "logo.png"

SLATE = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
LINE = colors.HexColor("#cbd5e1")
HEAD_BG = colors.HexColor("#e2e8f0")
INDIGO = colors.HexColor("#312e81")
GREEN_BG = colors.HexColor("#065f46")
GREEN_LT = colors.HexColor("#d1fae5")
AMBER_BG = colors.HexColor("#78350f")
AMBER_LT = colors.HexColor("#fef3c7")
ROSE_LT = colors.HexColor("#ffe4e6")
GREEN_TXT = colors.HexColor("#047857")
ROSE_TXT = colors.HexColor("#be123c")
AMBER_TXT = colors.HexColor("#b45309")


def _st() -> dict:
    return {
        "brand": ParagraphStyle(
            "brand", fontName=FONT_BOLD, fontSize=20, leading=23, textColor=INDIGO
        ),
        "sub": ParagraphStyle(
            "sub", fontName=FONT, fontSize=9, leading=12, textColor=MUTED
        ),
        "tiny": ParagraphStyle(
            "tiny", fontName=FONT, fontSize=7.5, leading=10, textColor=MUTED
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName=FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=INDIGO,
            spaceBefore=9,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", fontName=FONT, fontSize=8.5, leading=11.5, textColor=SLATE
        ),
        "cell": ParagraphStyle(
            "cell", fontName=FONT, fontSize=7.5, leading=9.5, textColor=SLATE
        ),
        "cellb": ParagraphStyle(
            "cellb", fontName=FONT_BOLD, fontSize=7.5, leading=9.5, textColor=SLATE
        ),
        "cellw": ParagraphStyle(
            "cellw", fontName=FONT_BOLD, fontSize=7.5, leading=9.5, textColor=colors.white
        ),
        "banner": ParagraphStyle(
            "banner", fontName=FONT_BOLD, fontSize=13, leading=16, textColor=colors.white
        ),
        "banner_r": ParagraphStyle(
            "banner_r",
            fontName=FONT,
            fontSize=9,
            leading=12,
            textColor=colors.white,
            alignment=2,
        ),
        "pass": ParagraphStyle(
            "pass", fontName=FONT_BOLD, fontSize=7.5, leading=9.5, textColor=GREEN_TXT
        ),
        "fail": ParagraphStyle(
            "fail", fontName=FONT_BOLD, fontSize=7.5, leading=9.5, textColor=ROSE_TXT
        ),
        "warn": ParagraphStyle(
            "warn", fontName=FONT_BOLD, fontSize=7.5, leading=9.5, textColor=AMBER_TXT
        ),
    }


def _grid(data, widths, header_bg=HEAD_BG, font_size=7.5):
    """Standard striped table style for the report."""
    return TableStyle(
        [
            ("FONT", (0, 0), (-1, -1), FONT, font_size),
            ("TEXTCOLOR", (0, 0), (-1, -1), SLATE),
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )


def _footer(canvas, doc_):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(
        15 * mm,
        9 * mm,
        "VeriGate decision-support report - AI advises, officers decide. "
        "This document is not itself an approval.",
    )
    canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Page {doc_.page}")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
    canvas.restoreState()


def _build_report_pdf(app: Application, db: Session, user: User) -> bytes:
    st = _st()
    esc = xiu.escape
    now = dt.datetime.utcnow().strftime("%d-%m-%Y %H:%M UTC")
    cfg_line = (
        f"OCR > {config.OCR_CONFIDENCE_THRESHOLD:.2f} · consistency > "
        f"{config.CONSISTENCY_THRESHOLD:.2f} · tamper < "
        f"{config.TAMPER_SCORE_THRESHOLD:.2f}"
    )

    story: list = []

    # ------------------------------------------------------------- header
    title_tbl = Table(
        [
            [Paragraph("VeriGate", st["brand"])],
            [
                Paragraph(
                    "Verification Report - AICTE Extension of Approval (EoA)",
                    st["sub"],
                )
            ],
        ],
        colWidths=[92 * mm],
    )
    title_tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    meta = Table(
        [
            [Paragraph(f"Reference: <b>{esc(_s(app.ref_no))}</b>", st["tiny"])],
            [Paragraph(f"Generated: {now}", st["tiny"])],
            [Paragraph(f"Requested by: {esc(_s(user.full_name))} ({user.role})", st["tiny"])],
        ],
        colWidths=[60 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    logo = (
        RLImage(str(_LOGO), width=15 * mm, height=15 * mm * 282 / 292)
        if _LOGO.exists()
        else ""
    )
    head = Table(
        [[logo, title_tbl, meta]],
        colWidths=[18 * mm, 100 * mm, 57 * mm],
    )
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [
        head,
        HRFlowable(width="100%", thickness=1, color=INDIGO, spaceAfter=6),
    ]

    # ------------------------------------------------------ verdict banner
    passed = app.status in ("VERIFIED", "APPROVED")
    gate_label = app.gate_status or (
        "VERIFIED" if passed else "INSUFFICIENT_EVIDENCE"
    )
    banner = Table(
        [
            [
                Paragraph(
                    f"EVIDENCE GATE: {_s(gate_label.replace('_', ' '))}", st["banner"]
                ),
                Paragraph(
                    f"Gate confidence <b>{app.gate_confidence:.2f}</b><br/>"
                    f"Risk {app.risk_score:.2f}",
                    st["banner_r"],
                ),
            ]
        ],
        colWidths=[115 * mm, 60 * mm],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN_BG if passed else AMBER_BG),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story += [banner, Spacer(1, 3 * mm)]

    for reason in app.gate_reasons or []:
        rid = reason.get("rule_id", "")
        msg = reason.get("message", "")
        story.append(
            Paragraph(
                f"<b>[{_s(rid)}]</b> {_s(msg)}",
                st["body"],
            )
        )
    story.append(
        Paragraph(
            "<i>Machine recommendation only - the final decision rests with the "
            "reviewing officer.</i>",
            st["tiny"],
        )
    )

    # --------------------------------------------------- application table
    story.append(Paragraph("1. Application under validation", st["h2"]))
    detail_rows = [
        ("Reference", app.ref_no, "Institution", app.institution_name),
        ("Category", app.category, "AICTE ID", app.aicte_id or "-"),
        ("Approved intake", str(app.approved_intake), "Address", app.address or "-"),
        ("Documents", str(len(app.documents)), "Flags raised", str(len(app.flags))),
        ("Submitted by", app.created_by, "Created", app.created_at.strftime("%d-%m-%Y %H:%M") if app.created_at else "-"),
        (
            "Validated",
            app.validated_at.strftime("%d-%m-%Y %H:%M") if app.validated_at else "not yet validated",
            "Workflow status",
            app.status.replace("_", " "),
        ),
        ("Mock issuer status", app.issuer_status or "-", "Open flags", str(sum(1 for f in app.flags if f.status == "OPEN"))),
        ("Demo scenario", app.scenario or "-", "MOCK_MODE", "ON (synthetic data)" if config.MOCK_MODE else "OFF"),
    ]
    details = Table(
        [[esc(_s(a)), esc(_s(b)), esc(_s(c)), esc(_s(d))] for a, b, c, d in detail_rows],
        colWidths=[28 * mm, 58 * mm, 30 * mm, 59 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), FONT_BOLD, 7.5),
                ("FONT", (2, 0), (2, -1), FONT_BOLD, 7.5),
                ("FONT", (1, 0), (1, -1), FONT, 7.5),
                ("FONT", (3, 0), (3, -1), FONT, 7.5),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(details)

    # ------------------------------------------------------------- signals
    story.append(Paragraph("2. Evidence Gate signals", st["h2"]))
    issuer_ok = app.issuer_status in ("VERIFIED", "NOT_REQUIRED", "")
    dupes = sum(1 for d in app.documents if d.duplicate_of)
    signal_rows = [
        [
            Paragraph("Signal", st["cellb"]),
            Paragraph("Value", st["cellb"]),
            Paragraph("Gate requirement", st["cellb"]),
            Paragraph("Result", st["cellb"]),
        ],
        [
            "OCR confidence",
            f"{app.ocr_confidence:.3f}",
            f"> {config.OCR_CONFIDENCE_THRESHOLD:.2f}",
            Paragraph("PASS" if app.ocr_confidence > config.OCR_CONFIDENCE_THRESHOLD else "FAIL", st["pass"] if app.ocr_confidence > config.OCR_CONFIDENCE_THRESHOLD else st["fail"]),
        ],
        [
            "Cross-record consistency (XGBoost)",
            f"{app.consistency_score:.3f}",
            f"> {config.CONSISTENCY_THRESHOLD:.2f}",
            Paragraph("PASS" if app.consistency_score >= config.CONSISTENCY_THRESHOLD else "FAIL", st["pass"] if app.consistency_score >= config.CONSISTENCY_THRESHOLD else st["fail"]),
        ],
        [
            "Tamper score (ELA)",
            f"{app.tamper_score:.3f}",
            f"< {config.TAMPER_SCORE_THRESHOLD:.2f}",
            Paragraph("PASS" if app.tamper_score < config.TAMPER_SCORE_THRESHOLD else "FAIL", st["pass"] if app.tamper_score < config.TAMPER_SCORE_THRESHOLD else st["fail"]),
        ],
        [
            "Issuer portal check",
            app.issuer_status or "-",
            "all checks VERIFIED",
            Paragraph("PASS" if issuer_ok else "FAIL", st["pass"] if issuer_ok else st["fail"]),
        ],
        [
            "Duplicate documents (pHash)",
            str(dupes),
            "0 duplicates",
            Paragraph("PASS" if dupes == 0 else "FAIL", st["pass"] if dupes == 0 else st["fail"]),
        ],
        [
            "CRITICAL flags",
            str(sum(1 for f in app.flags if f.severity == "CRITICAL")),
            "0 critical",
            Paragraph(
                "PASS" if not any(f.severity == "CRITICAL" for f in app.flags) else "FAIL",
                st["pass"] if not any(f.severity == "CRITICAL" for f in app.flags) else st["fail"],
            ),
        ],
    ]
    signals = Table(signal_rows, colWidths=[55 * mm, 30 * mm, 45 * mm, 45 * mm])
    signals.setStyle(_grid([[]], []))
    story.append(signals)
    story.append(
        Paragraph(
            f"Gate rule: {cfg_line} AND every issuer portal VERIFIED - "
            "any single failure makes the gate abstain.",
            st["tiny"],
        )
    )

    # --------------------------------------------------------------- flags
    story.append(Paragraph("3. Explainable flags", st["h2"]))
    sev_order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    flags = sorted(
        app.flags, key=lambda f: (sev_order.get(f.severity, 3), f.rule_id)
    )
    flag_rows = [
        [
            Paragraph("Rule", st["cellb"]),
            Paragraph("Severity", st["cellb"]),
            Paragraph("Finding", st["cellb"]),
            Paragraph("Location", st["cellb"]),
        ]
    ]
    for f in flags:
        where = []
        if f.document_id:
            where.append(f"document #{f.document_id}")
        if f.page_no:
            where.append(f"page {f.page_no}")
        if f.bbox:
            where.append("bbox [" + ", ".join(f"{v:.2f}" for v in f.bbox) + "]")
        flag_rows.append(
            [
                Paragraph(_s(f.rule_id), st["cellb"]),
                Paragraph(
                    _s(f.severity),
                    st["fail"]
                    if f.severity == "CRITICAL"
                    else (st["warn"] if f.severity == "WARN" else st["cell"]),
                ),
                Paragraph(esc(f"{f.title} - {f.reason}"), st["cell"]),
                Paragraph(esc(" · ".join(where) or "-"), st["cell"]),
            ]
        )
    if not flags:
        flag_rows.append(
            [
                Paragraph("-", st["cell"]),
                Paragraph("-", st["cell"]),
                Paragraph(
                    "No flags raised - nothing in the evidence required reporting.",
                    st["cell"],
                ),
                Paragraph("-", st["cell"]),
            ]
        )
    story.append(
        Table(
            flag_rows,
            colWidths=[24 * mm, 16 * mm, 100 * mm, 35 * mm],
            style=_grid([[]], []),
        )
    )

    # ----------------------------------------------------------- checklist
    story.append(Paragraph("4. APH 2024-27 auto-checklist", st["h2"]))
    chk_rows = [
        [
            Paragraph("Rule", st["cellb"]),
            Paragraph("Requirement", st["cellb"]),
            Paragraph("Status", st["cellb"]),
            Paragraph("Notes", st["cellb"]),
        ]
    ]
    for item in app.checklist_json or []:
        notes = []
        if item.get("present"):
            if item.get("document_id"):
                notes.append(f"document #{item['document_id']}")
        else:
            notes.append("not uploaded")
        if item.get("issuer_status"):
            notes.append(f"issuer: {item['issuer_status']}")
        if item.get("expiry_date"):
            notes.append(f"expired {item['expiry_date']}")
        if item.get("missing_fields"):
            notes.append("missing: " + ", ".join(item["missing_fields"]))
        status = item.get("status", "-")
        status_style = (
            st["pass"]
            if status == "OK"
            else (st["fail"] if status == "MISSING" else st["warn"])
        )
        chk_rows.append(
            [
                Paragraph(_s(item.get("rule_id", "-")), st["cellb"]),
                Paragraph(esc(_s(item.get("name", "-"))), st["cell"]),
                Paragraph(_s(status), status_style),
                Paragraph(esc(" · ".join(notes) or "-"), st["cell"]),
            ]
        )
    story.append(
        Table(
            chk_rows,
            colWidths=[24 * mm, 70 * mm, 20 * mm, 61 * mm],
            style=_grid([[]], []),
        )
    )

    # ----------------------------------------------------------- decisions
    reviews = sorted(app.reviews, key=lambda r: r.created_at)
    if reviews:
        story.append(Paragraph("5. Human decisions (audit trail)", st["h2"]))
        dec_rows = [
            [
                Paragraph("When", st["cellb"]),
                Paragraph("Reviewer", st["cellb"]),
                Paragraph("Decision", st["cellb"]),
                Paragraph("Comment", st["cellb"]),
            ]
        ]
        for r in reviews:
            dec_rows.append(
                [
                    Paragraph(r.created_at.strftime("%d-%m-%Y %H:%M"), st["cell"]),
                    Paragraph(esc(_s(r.reviewer_name)), st["cell"]),
                    Paragraph(_s(r.decision), st["cellb"]),
                    Paragraph(esc(_s(r.comment) or "-"), st["cell"]),
                ]
            )
        story.append(
            Table(
                dec_rows,
                colWidths=[32 * mm, 45 * mm, 30 * mm, 68 * mm],
                style=_grid([[]], []),
            )
        )

    # --------------------------------------------------- signature blocks
    story.append(Paragraph("Sign-off", st["h2"]))
    sig = Table(
        [
            [
                Paragraph("Machine recommendation (VeriGate Evidence Gate)", st["tiny"]),
                Paragraph("Final decision (reviewing officer)", st["tiny"]),
            ],
            [
                Paragraph(
                    "<br/><br/>______________________________<br/>"
                    f"{_s(gate_label.replace('_', ' '))} · confidence "
                    f"{app.gate_confidence:.2f}",
                    st["cell"],
                ),
                Paragraph(
                    "<br/><br/>______________________________<br/>"
                    "Name / signature / date",
                    st["cell"],
                ),
            ],
        ],
        colWidths=[87 * mm, 88 * mm],
    )
    sig.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(sig)
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Generated by VeriGate in MOCK_MODE with synthetic data. "
            "Evidence Gate thresholds are configuration, not law: "
            f"{cfg_line}. Every flag above carries a rule ID, document, page "
            "and bounding box so the reasoning can be re-checked by a human.",
            st["tiny"],
        )
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=15 * mm,
        title=f"VeriGate verification report - {app.ref_no}",
        author="VeriGate",
        subject="AICTE Extension of Approval validation",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ---------------------------------------------------------------- endpoints
@router.get("/applications/{app_id}/report")
def verification_report(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Downloadable A4 verification report: verdict, signals, every flag with
    its coordinates, the APH checklist and a human sign-off block."""
    if not _RL_AVAILABLE:
        raise HTTPException(503, "PDF engine (reportlab) is not available")
    app = _get_app(db, app_id)
    pdf = _build_report_pdf(app, db, user)
    filename = f"VeriGate_{app.ref_no.replace('/', '-')}_report.pdf"
    audit(
        db,
        "REPORT_EXPORT",
        actor=user.username,
        role=user.role,
        entity_type="application",
        entity_id=app.id,
        detail={"ref_no": app.ref_no, "filename": filename, "bytes": len(pdf)},
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/applications/{app_id}/consistency")
def consistency_view(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Side-by-side: values submitted on the application vs the AICTE master
    record the XGBoost consistency model compared them against."""
    app = _get_app(db, app_id)
    feats = _consistency_features(app, db)

    record = None
    if app.aicte_id:
        record = (
            db.query(MockRecord).filter(MockRecord.aicte_id == app.aicte_id).first()
        )

    extracted: dict[str, str] = {}
    for doc in app.documents:
        fields = doc.extracted_json or {}
        for key in (
            "institution_name",
            "aicte_id",
            "approved_intake",
            "issue_date",
            "expiry_date",
        ):
            extracted[key] = extracted.get(key) or field_value(fields, key) or ""

    def classify(feature: str, submitted: Any, has_record: bool) -> str:
        value = float(feats.get(feature, 0.0))
        if not has_record:
            return "NO_RECORD"
        if str(submitted).strip() in ("", "-", "—"):
            return "NOT_EXTRACTED"
        if value >= 0.9:
            return "MATCH"
        if value >= 0.5:
            return "PARTIAL"
        return "MISMATCH"

    has_record = record is not None
    valid_upto = f"valid up to {record.valid_upto}" if record else ""
    rows = [
        {
            "field": "Institution name",
            "submitted": app.institution_name,
            "master": record.institution_name if record else "",
            "feature": "name_sim",
            "value": float(feats.get("name_sim", 0.0)),
            "status": classify("name_sim", app.institution_name, has_record),
        },
        {
            "field": "AICTE ID",
            "submitted": app.aicte_id or "",
            "master": record.aicte_id if record else "",
            "feature": "aicte_id_match",
            "value": float(feats.get("aicte_id_match", 0.0)),
            "status": classify("aicte_id_match", app.aicte_id, has_record),
        },
        {
            "field": "Category",
            "submitted": app.category,
            "master": record.category if record else "",
            "feature": "category_match",
            "value": float(feats.get("category_match", 0.0)),
            "status": classify("category_match", app.category, has_record),
        },
        {
            "field": "Address",
            "submitted": app.address or "",
            "master": record.address if record else "",
            "feature": "address_sim",
            "value": float(feats.get("address_sim", 0.0)),
            "status": classify("address_sim", app.address, has_record),
        },
        {
            "field": "Approved intake",
            "submitted": str(app.approved_intake or 0),
            "master": str(record.approved_intake) if record else "",
            "feature": "intake_match",
            "value": float(feats.get("intake_match", 0.0)),
            "status": classify("intake_match", str(app.approved_intake or 0), has_record),
        },
        {
            "field": "Issue date vs validity window",
            "submitted": extracted.get("issue_date", ""),
            "master": valid_upto,
            "feature": "issue_plausible",
            "value": float(feats.get("issue_plausible", 0.0)),
            "status": classify(
                "issue_plausible", extracted.get("issue_date", ""), has_record
            ),
        },
        {
            "field": "Expiry date vs record validity",
            "submitted": extracted.get("expiry_date", ""),
            "master": valid_upto,
            "feature": "expiry_aligned",
            "value": float(feats.get("expiry_aligned", 0.0)),
            "status": classify(
                "expiry_aligned", extracted.get("expiry_date", ""), has_record
            ),
        },
    ]

    score = consistency.score(feats)
    weakest = consistency.top_features(feats, 4)
    return {
        "score": score,
        "stored_score": app.consistency_score,
        "threshold": config.CONSISTENCY_THRESHOLD,
        "below_threshold": score < config.CONSISTENCY_THRESHOLD,
        "model": consistency.status(),
        "weakest_features": weakest,
        "master_record": (
            {
                "aicte_id": record.aicte_id,
                "institution_name": record.institution_name,
                "category": record.category,
                "address": record.address,
                "approved_intake": record.approved_intake,
                "status": record.status,
                "valid_upto": record.valid_upto,
            }
            if record
            else None
        ),
        "rows": rows,
        "features": feats,
    }


def _doc_ref(doc: Document, app: Optional[Application]) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "page_count": doc.page_count,
        "application_id": doc.application_id,
        "ref_no": app.ref_no if app else "?",
        "institution_name": app.institution_name if app else "?",
    }


@router.get("/applications/{app_id}/duplicates")
def duplicates_view(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Every pHash duplicate found for this application: the submitted copy,
    the original (donor) it matches, and the distance that proved it."""
    app = _get_app(db, app_id)
    pairs = []
    for doc in app.documents:
        if not doc.duplicate_of:
            continue
        donor = db.get(Document, doc.duplicate_of)
        if not donor:
            continue
        donor_app = db.get(Application, donor.application_id)
        distance = (
            tamper.hamming(doc.phash, donor.phash)
            if doc.phash and donor.phash
            else None
        )
        pairs.append(
            {
                "rule_id": "APH-GEN-D01",
                "document": _doc_ref(doc, app),
                "donor": _doc_ref(donor, donor_app),
                "distance": distance,
                "threshold": tamper.duplicate_threshold(),
                "text_sim": round(
                    name_similarity(doc.ocr_text or "", donor.ocr_text or ""), 3
                ),
                "page": 1,
            }
        )
    return {"pairs": pairs, "count": len(pairs)}


# ----------------------------------------------------------- issuer portals
@router.get("/issuer/status")
def issuer_status_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Health + live outcomes for every mock issuer portal. The check outcomes
    are recomputed by calling the same read-only verify() the pipeline uses,
    so this page always reflects the current document set."""
    checks: dict[str, Counter] = {pid: Counter() for pid in PORTALS}
    examples: dict[str, dict[str, list]] = {
        pid: defaultdict(list) for pid in PORTALS
    }
    last_checked: dict[str, Optional[dt.datetime]] = {pid: None for pid in PORTALS}

    for app in db.query(Application).order_by(Application.id).all():
        for item in app.checklist_json or []:
            portal = item.get("issuer_portal")
            doc_id = item.get("document_id")
            if not portal or portal not in PORTALS or not doc_id:
                continue
            doc = db.get(Document, int(doc_id))
            if not doc or doc.application_id != app.id:
                continue
            fields = doc.extracted_json or {}
            try:
                res = mock_verify(
                    db,
                    portal,
                    field_value(fields, "doc_number") or "",
                    field_value(fields, "qr_token") or "",
                    field_value(fields, "signature") or "",
                )
            except Exception:
                continue
            status = res.get("status", "MANUAL_REVIEW")
            checks[portal][status] += 1
            if status != "VERIFIED" and len(examples[portal][status]) < 4:
                examples[portal][status].append(app.ref_no)
            if app.validated_at and (
                last_checked[portal] is None
                or app.validated_at > last_checked[portal]
            ):
                last_checked[portal] = app.validated_at

    records = db.query(IssuerRecord).all()
    rec_count = Counter(r.portal for r in records)
    rec_down = Counter(r.portal for r in records if r.source_unavailable)
    pinned = [
        {
            "portal": r.portal,
            "portal_name": PORTALS.get(r.portal, r.portal),
            "doc_number": r.doc_number,
            "holder_name": r.holder_name,
        }
        for r in records
        if r.source_unavailable
    ]

    portals = []
    for pid, name in PORTALS.items():
        c = checks[pid]
        total = sum(c.values())
        failures = {k: v for k, v in c.items() if k != "VERIFIED"}
        portals.append(
            {
                "id": pid,
                "name": name,
                "status": "DOWN" if pid in OUTAGE else "UP",
                "degraded": rec_down[pid] > 0,
                "records": rec_count[pid],
                "records_down": rec_down[pid],
                "checks_total": total,
                "checks": dict(c),
                "verified": c.get("VERIFIED", 0),
                "verified_rate": (
                    round(c.get("VERIFIED", 0) / total, 3) if total else None
                ),
                "failures": failures,
                "examples": {k: v for k, v in examples[pid].items()},
                "last_checked": (
                    last_checked[pid].strftime("%d-%m-%Y %H:%M")
                    if last_checked[pid]
                    else ""
                ),
            }
        )

    all_checks: Counter = Counter()
    for c in checks.values():
        all_checks.update(c)
    total_checks = sum(all_checks.values())
    return {
        "portals": portals,
        "outage_portals": sorted(OUTAGE),
        "pinned_outages": pinned,
        "summary": {
            "portals": len(portals),
            "down": sum(1 for p in portals if p["status"] == "DOWN"),
            "degraded": sum(1 for p in portals if p["degraded"]),
            "total_checks": total_checks,
            "verified": all_checks.get("VERIFIED", 0),
            "verified_rate": (
                round(all_checks.get("VERIFIED", 0) / total_checks, 3)
                if total_checks
                else 0.0
            ),
            "by_status": dict(all_checks),
        },
        "updated_at": dt.datetime.utcnow().strftime("%d-%m-%Y %H:%M UTC"),
    }


# ---------------------------------------------------------------- analytics
@router.get("/dashboard/analytics")
def analytics_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Portfolio-level trends for the Analytics page: gate outcomes, category
    pass rates, which rules fire most, document gaps, issuer outcomes, risk
    distribution and how long files sit in the queue."""
    apps = db.query(Application).all()
    flags = db.query(Flag).all()
    reviews = db.query(ReviewDecision).all()

    def avg(values: list[float]) -> float:
        vals = [float(v or 0.0) for v in values]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    status_counts = Counter(a.status for a in apps)
    total = len(apps)
    verified = status_counts.get("VERIFIED", 0)
    insufficient = status_counts.get("INSUFFICIENT_EVIDENCE", 0)
    decided = verified + insufficient

    # ---------------------------------------------------------- by category
    by_category = []
    for cat in sorted({a.category for a in apps}):
        rows = [a for a in apps if a.category == cat]
        by_category.append(
            {
                "category": cat,
                "total": len(rows),
                "verified": sum(1 for a in rows if a.status == "VERIFIED"),
                "insufficient": sum(
                    1 for a in rows if a.status == "INSUFFICIENT_EVIDENCE"
                ),
                "avg_confidence": avg([a.gate_confidence for a in rows]),
                "avg_risk": avg([a.risk_score for a in rows]),
            }
        )

    # --------------------------------------------------------------- flags
    by_kind_counter = Counter(f.kind for f in flags)
    critical_by_kind = Counter(f.kind for f in flags if f.severity == "CRITICAL")
    flags_by_kind = [
        {
            "kind": kind,
            "count": count,
            "critical": critical_by_kind.get(kind, 0),
        }
        for kind, count in by_kind_counter.most_common()
    ]

    rule_titles: dict[str, tuple] = {}
    rule_counts: Counter = Counter()
    for f in flags:
        rule_counts[f.rule_id] += 1
        rule_titles.setdefault(f.rule_id, (f.title, f.severity))
    flags_by_rule = [
        {
            "rule_id": rid,
            "title": rule_titles[rid][0],
            "severity": rule_titles[rid][1],
            "count": count,
        }
        for rid, count in rule_counts.most_common(10)
    ]

    # ------------------------------------------- document gaps (checklist)
    gap_counts: Counter = Counter()
    gap_rules: dict[tuple, str] = {}
    for a in apps:
        for item in a.checklist_json or []:
            status = item.get("status")
            if status in ("MISSING", "EXPIRED"):
                key = (status, item.get("name", "?"))
                gap_counts[key] += 1
                gap_rules.setdefault(key, item.get("rule_id", ""))
    document_gaps = [
        {
            "name": name,
            "status": status,
            "rule_id": gap_rules[(status, name)],
            "count": count,
        }
        for (status, name), count in gap_counts.most_common()
    ]

    # ------------------------------------------------------- issuer outcome
    issuer_outcomes = [
        {"status": st, "count": n}
        for st, n in Counter(a.issuer_status for a in apps if a.issuer_status).most_common()
    ]

    # ------------------------------------------- why the gate abstained
    abstain_reasons: Counter = Counter()
    for a in apps:
        for r in a.gate_reasons or []:
            rid = (r or {}).get("rule_id") or "?"
            abstain_reasons[rid] += 1
    abstain = [
        {"rule_id": rid, "count": n} for rid, n in abstain_reasons.most_common()
    ]

    # ------------------------------------------------------- risk buckets
    risk_edges = [
        ("0.00 - 0.20", 0.0, 0.2),
        ("0.20 - 0.40", 0.2, 0.4),
        ("0.40 - 0.60", 0.4, 0.6),
        ("0.60 - 0.80", 0.6, 0.8),
        ("0.80 - 1.00", 0.8, 1.0001),
    ]
    risk_buckets = [
        {
            "bucket": label,
            "count": sum(1 for a in apps if lo <= a.risk_score < hi),
        }
        for label, lo, hi in risk_edges
    ]

    # -------------------------------------------------------- queue aging
    now = dt.datetime.utcnow()
    aging_edges = [
        ("< 1 hour", 0, 1),
        ("1 - 6 hours", 1, 6),
        ("6 - 24 hours", 6, 24),
        ("> 24 hours", 24, 10_000_000),
    ]
    pending = {"UPLOADED", "PROCESSING", "INSUFFICIENT_EVIDENCE", "IN_REVIEW"}
    queue_aging = []
    for label, lo, hi in aging_edges:
        n = 0
        for a in apps:
            if a.status not in pending or not a.created_at:
                continue
            age_h = (now - a.created_at).total_seconds() / 3600.0
            if lo <= age_h < hi:
                n += 1
        queue_aging.append({"bucket": label, "count": n})

    decisions = Counter(r.decision for r in reviews)

    return {
        "generated_at": now.strftime("%d-%m-%Y %H:%M UTC"),
        "totals": {
            "applications": total,
            "verified": verified,
            "insufficient_evidence": insufficient,
            "in_review": status_counts.get("IN_REVIEW", 0),
            "approved": status_counts.get("APPROVED", 0),
            "rejected": status_counts.get("REJECTED", 0),
            "pending": sum(status_counts.get(s, 0) for s in pending),
            "gate_pass_rate": round(verified / decided, 3) if decided else 0.0,
            "flags": len(flags),
            "open_flags": sum(1 for f in flags if f.status == "OPEN"),
            "documents": db.query(Document).count(),
        },
        "averages": {
            "ocr_confidence": avg([a.ocr_confidence for a in apps]),
            "consistency": avg([a.consistency_score for a in apps]),
            "tamper": avg([a.tamper_score for a in apps]),
            "gate_confidence": avg([a.gate_confidence for a in apps]),
            "risk": avg([a.risk_score for a in apps]),
        },
        "gate_outcomes": [
            {"status": st, "count": n}
            for st, n in status_counts.most_common()
        ],
        "by_category": by_category,
        "flags_by_kind": flags_by_kind,
        "flags_by_rule": flags_by_rule,
        "document_gaps": document_gaps,
        "issuer_outcomes": issuer_outcomes,
        "abstain_reasons": abstain,
        "risk_buckets": risk_buckets,
        "queue_aging": queue_aging,
        "decisions": {
            "APPROVE": decisions.get("APPROVE", 0),
            "REJECT": decisions.get("REJECT", 0),
            "REQUEST_INFO": decisions.get("REQUEST_INFO", 0),
        },
        "scenarios": {
            a.scenario: {"ref_no": a.ref_no, "status": a.status}
            for a in apps
            if a.scenario
        },
    }
