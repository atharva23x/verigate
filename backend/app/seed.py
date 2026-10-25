"""Seed script: synthetic data for the VeriGate demo (NO real data anywhere).

Creates on first startup:
  * 4 users (officers, reviewer, auditor - all passwords documented in README)
  * 30 fake applications: 10 clean, 8 missing docs, 5 expired, 4 tampered,
    3 duplicates, with generated PDFs (ReportLab) + mock OCR ground truth
  * mock AICTE master records + mock issuer-portal records (signed with HMAC)
  * runs the full validation pipeline on all 30 so the dashboard is alive

Demo scenarios (tagged in Application.scenario):
  A -> app 1  clean                       -> VERIFIED
  B -> app 11 missing mandatory document  -> flagged by rule ID
  C -> app 24 tampered date (ELA region)  -> red bounding-box overlay
  D -> app 5  issuer portal down          -> SOURCE_UNAVAILABLE, not blocked
  E -> app 6  low OCR confidence          -> INSUFFICIENT_EVIDENCE -> review queue
"""

import datetime as dt
import json
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from . import config
from .audit import audit
from .database import SessionLocal
from .mock_issuer_api import signature_for
from .models import Application, Document, IssuerRecord, MockRecord, User
from .security import hash_password
from .services import pipeline, rules_engine

PW, PH = A4  # 595.27 x 841.89 pt

USERS = [
    ("officer1", "officer123", "officer", "Atharva Bhangale"),
    ("reviewer1", "reviewer123", "reviewer", "Nayan Khune (Review Officer)"),
    ("auditor1", "auditor123", "auditor", "Tejas Bagade (Auditor)"),
]

# Realistic-looking but entirely fake institution names - 10 per category,
# assigned in seeding order (application index -> position within category).
INSTITUTION_NAMES = {
    "Engineering": [
        "Sri Venkateswara Institute of Technology",
        "Swami Vivekananda College of Engineering",
        "Netaji Institute of Technology & Sciences",
        "Raman Institute of Technology",
        "Bharati College of Engineering & Technology",
        "Saraswati Institute of Technology",
        "Chhatrapati College of Engineering",
        "Guru Gobind Institute of Technology",
        "Jamuna Institute of Technology",
        "Sir M. Visvesvaraya College of Engineering",
    ],
    "Management": [
        "Vivekananda Institute of Management",
        "Netaji School of Management",
        "Bharati Institute of Management & Commerce",
        "Saraswati Institute of Management",
        "Guru Gobind Business School",
        "Raman College of Management",
        "Anna Institute of Business Administration",
        "Chhatrapati Institute of Management",
        "Swami Vivekananda School of Business",
        "Jamuna Institute of Management",
    ],
    "Pharmacy": [
        "Sri Raman College of Pharmacy",
        "Saraswati Institute of Pharmaceutical Sciences",
        "Bharati College of Pharmacy",
        "Swami Vivekananda Institute of Pharmacy",
        "Jamuna College of Pharmacy",
        "Netaji Institute of Pharmaceutical Education",
        "Anna College of Pharmacy",
        "Chhatrapati Institute of Pharmacy",
        "Guru Gobind College of Pharmacy",
        "Sir M. Visvesvaraya Institute of Pharmaceutical Sciences",
    ],
}

# (city, state code, PIN root, localities) - the order preserves the original
# state cycle so seeded document numbers stay stable (app 5 must remain
# Kolkata/WB -> FIRE/WB/2026/0053, asserted by test_insights.py).
CITIES = [
    ("New Delhi", "DL", "110",
     ["Karol Bagh", "Lajpat Nagar", "Rohini", "Saket"]),
    ("Mumbai", "MH", "400",
     ["Andheri East", "Dadar West", "Powai", "Bandra West"]),
    ("Bengaluru", "KA", "560",
     ["Koramangala", "Jayanagar", "Whitefield", "Rajajinagar"]),
    ("Chennai", "TN", "600",
     ["T. Nagar", "Anna Nagar", "Adyar", "Velachery"]),
    ("Kolkata", "WB", "700",
     ["Salt Lake", "Behala", "Gariahat", "New Town"]),
    ("Lucknow", "UP", "226",
     ["Gomti Nagar", "Hazratganj", "Aliganj", "Indira Nagar"]),
    ("Jaipur", "RJ", "302",
     ["Vaishali Nagar", "Malviya Nagar", "C-Scheme", "Mansarovar"]),
    ("Ahmedabad", "GJ", "380",
     ["Navrangpura", "Satellite", "Maninagar", "Bodakdev"]),
]

# Annual student intake AICTE typically approves per programme, by stream.
INTAKE_BY_CATEGORY = {
    "Engineering": [60, 120, 120, 180, 60],
    "Management": [60, 90, 120, 60],
    "Pharmacy": [60, 100, 60, 120],
}

DOC_PREFIX = {
    "PREV_EOA_LETTER": "EOA",
    "FIRE_SAFETY_NOC": "FIRE",
    "BUILDING_STABILITY_CERT": "STRUCT",
    "PREMISES_NOC": "PREM",
    "PHARMACY_REG_CERT": "PCI",
    "LAND_OWNERSHIP_DEED": "LAND",
    "LEASE_DEED": "LEASE",
    "AFFIDAVIT_UNDERTAKING": "AFF",
    "EOA_FORM": "APP",
}

DOC_TITLES = {
    "EOA_FORM": "EXTENSION OF APPROVAL APPLICATION FORM (APH 2024-27)",
    "PREV_EOA_LETTER": "AICTE EXTENSION OF APPROVAL - PREVIOUS YEAR LETTER",
    "FIRE_SAFETY_NOC": "FIRE & EMERGENCY SAFETY NO OBJECTION CERTIFICATE",
    "BUILDING_STABILITY_CERT": "BUILDING STRUCTURAL STABILITY CERTIFICATE",
    "PREMISES_NOC": "PREMISES NO OBJECTION CERTIFICATE",
    "PHARMACY_REG_CERT": "PHARMACY COUNCIL APPROVAL / REGISTRATION CERTIFICATE",
    "LAND_OWNERSHIP_DEED": "LAND OWNERSHIP DEED (CERTIFIED COPY)",
    "LEASE_DEED": "CAMPUS LEASE DEED (30 YEARS)",
    "AFFIDAVIT_UNDERTAKING": "AFFIDAVIT OF UNDERTAKING (Rs. 10 STAMP)",
}

AUTHORITIES = {
    "aicte_portal": "AICTE, New Delhi",
    "fire_dept": "State Fire & Emergency Services Directorate",
    "state_board": "State Technical Education Board",
    "pharmacy_council": "Pharmacy Council of India",
    "": "Notary / Sub-Divisional Magistrate",
}


# --------------------------------------------------------------------- PDF bits
class DocWriter:
    """Draws a synthetic document and records a per-word OCR ground truth
    (normalized boxes + confidence) for the mock OCR engine."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.c = canvas.Canvas(str(self.path), pagesize=A4)
        self.tokens: list[dict] = []
        self.y = 96.0
        self.x = 60.0
        self.conf = 0.965      # overwritten for degraded (scenario E) docs
        self.jitter = 0.0

    def line(self, text: str, size: int = 10, bold: bool = False,
             gap: float = 20.0, conf: float | None = None):
        font = "Helvetica-Bold" if bold else "Helvetica"
        self.c.setFont(font, size)
        self.c.drawString(self.x, PH - self.y - size, text)
        cx = self.x
        space_w = pdfmetrics.stringWidth(" ", font, size)
        rng = random.Random(hash(text) & 0xFFFF)
        base_conf = self.conf if conf is None else conf
        for word in text.split(" "):
            w = pdfmetrics.stringWidth(word, font, size)
            x0, x1 = cx / PW, (cx + w) / PW
            y0, y1 = self.y / PH, (self.y + size * 1.35) / PH
            if self.jitter:
                x0 += rng.uniform(-self.jitter, self.jitter)
                x1 += rng.uniform(-self.jitter, self.jitter)
                y0 += rng.uniform(-self.jitter, self.jitter)
                y1 += rng.uniform(-self.jitter, self.jitter)
            self.tokens.append(
                {
                    "text": word,
                    "box": [
                        round(min(x0, x1), 4), round(min(y0, y1), 4),
                        round(max(x0, x1), 4), round(max(y0, y1), 4),
                    ],
                    "conf": round(
                        max(0.05, min(0.999, base_conf + rng.uniform(-0.03, 0.03))), 4
                    ),
                }
            )
            cx += w + space_w
        self.y += gap

    def stamp_line(self, text: str, size: int = 10, gap: float = 20.0,
                   quality: int = 52):
        """A tampered line: text rendered as a low-quality JPEG pasted into the
        PDF. ELA detects exactly this kind of recompressed region."""
        font = "Helvetica"
        w_pt = pdfmetrics.stringWidth(text, font, size)
        h_pt = size * 1.6
        scale = 3
        img = Image.new("RGB", (max(2, int(w_pt * scale)), max(2, int(h_pt * scale))), "white")
        draw = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.load_default(size=int(h_pt * scale * 0.58))
        except TypeError:  # older Pillow
            fnt = ImageFont.load_default()
        draw.text((5, 3), text, fill=(15, 15, 15), font=fnt)
        tmp = self.path.with_suffix(".stamp.jpg")
        img.save(tmp, "JPEG", quality=quality)
        self.c.drawImage(
            ImageReader(str(tmp)), self.x, PH - self.y - h_pt, width=w_pt, height=h_pt
        )
        self.tokens.append(
            {
                "text": text,
                "box": [
                    round(self.x / PW, 4), round(self.y / PH, 4),
                    round((self.x + w_pt) / PW, 4), round((self.y + h_pt) / PH, 4),
                ],
                "conf": 0.93,
            }
        )
        self.y += gap

    def save(self):
        self.c.save()
        stamp = self.path.with_suffix(".stamp.jpg")
        if stamp.exists():
            stamp.unlink()


def build_document(path: Path, doc_type: str, req: dict, ctx: dict,
                   tamper: bool = False, degraded: bool = False):
    """Render one synthetic document.

    Returns (ground_truth_tokens, tamper_gt) where tamper_gt carries the seeded
    region for demo scenario C (used only when MOCK_MODE=True).
    """
    w = DocWriter(path)
    if degraded:  # scenario E: smudged scan -> low, noisy OCR confidence
        w.conf, w.jitter = 0.45, 0.004

    w.line("GOVERNMENT OF INDIA", size=9, gap=14)
    w.line("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", size=12, bold=True, gap=26)
    w.line(DOC_TITLES.get(doc_type, doc_type), size=11, bold=True, gap=24)
    w.line("-" * 72, size=8, gap=16)
    w.line(f"Institution: {ctx['name']}")
    w.line(f"AICTE ID: {ctx['aicte_id']}")
    if doc_type == "EOA_FORM":
        w.line(f"Approved Intake: {ctx['intake']}")
        w.line(f"Programme: {ctx['programme']}")
        w.line(f"Application No: {ctx['doc_number']}")
        w.line(f"Dated: {ctx['issue']}")
    else:
        w.line(f"Doc No: {ctx['doc_number']}")
        if tamper:
            # The altered date, pasted in as a JPEG - the flagged ELA region
            w.stamp_line(f"Date of Issue: {ctx['altered_issue']}")
        else:
            w.line(f"Date of Issue: {ctx['issue']}")
        if req.get("validity_required"):
            w.line(f"Valid up to: {ctx['expiry']}")
        w.line(f"Address: {ctx['address']}")
    w.line(f"QR: {ctx['qr']}")
    w.line(f"SIGN: {ctx['sig']}")
    w.line(f"Issuing Authority: {ctx['authority']}")
    w.line("-" * 72, size=8, gap=14)
    w.line("Synthetic prototype document - no legal value.", size=8)
    w.save()
    tamper_gt = None
    if tamper and w.tokens:
        # The last "Date of Issue" token is the pasted stamp - hand its region
        # to the pipeline as MOCK ground truth so scenario C is deterministic.
        for tok in reversed(w.tokens):
            if tok["text"].startswith("Date"):
                x0, y0, x1, y1 = tok["box"]
                tamper_gt = {
                    "bbox": [x0, y0, round(x1 - x0, 4), round(y1 - y0, 4)],
                    "score": 0.87,
                    "note": "pasted JPEG date stamp (altered from "
                            f"{ctx['issue']} to {ctx['altered_issue']})",
                }
                break
    return w.tokens, tamper_gt


# ------------------------------------------------------------------------ plan
def _plan() -> list[dict]:
    cats = ["Engineering", "Management", "Pharmacy"]
    plan = []
    for i in range(1, 31):
        if i <= 10:
            kind = "clean"
        elif i <= 18:
            kind = "missing"
        elif i <= 23:
            kind = "expired"
        elif i <= 27:
            kind = "tampered"
        else:
            kind = "duplicate"
        plan.append({"idx": i, "kind": kind, "category": cats[(i - 1) % 3],
                     "scenario": "", "title": ""})
    by = {p["idx"]: p for p in plan}
    by[1].update(scenario="A", title="Clean application -> VERIFIED")
    by[11].update(scenario="B", title="Missing mandatory document",
                  missing="FIRE_SAFETY_NOC")
    by[24].update(scenario="C", title="Tampered date -> ELA overlay", tamper=True)
    by[5].update(scenario="D", title="Issuer portal down -> SOURCE_UNAVAILABLE",
                 outage=True)
    by[6].update(scenario="E", title="Low OCR confidence -> manual review",
                 degraded=True)
    # All four 'tampered' apps (24-27) carry an altered, pasted date stamp;
    # app 24 is simply the one tagged as demo scenario C.
    for p in plan:
        if p["kind"] == "tampered":
            p["tamper"] = True
    # Remaining 'missing' apps drop a pseudo-random mandatory doc
    rng = random.Random(7)
    for p in plan:
        if p["kind"] == "missing" and "missing" not in p:
            options = [
                r["doc_type"]
                for r in rules_engine.category_rules(p["category"])
                if r["doc_type"] != "EOA_FORM"
            ]
            p["missing"] = rng.choice(options)
    return plan


# ------------------------------------------------------------------- seeding
def seed_if_empty() -> bool:
    """Populate the DB on first startup. Returns True if seeding happened."""
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("[seed] database already seeded - skipping")
            return False

        print("[seed] seeding users, synthetic applications, issuer records ...")
        audit(db, "SEED_START", actor="seed", detail={"applications": 30})
        for username, password, role, full_name in USERS:
            db.add(
                User(username=username, password_hash=hash_password(password),
                     role=role, full_name=full_name)
            )
        db.commit()

        rng = random.Random(20261024)
        plan = _plan()
        today = dt.datetime.utcnow().date()
        future_expiry = f"31-03-{today.year + 1}"
        past_expiry = f"31-03-{today.year - 2}"

        donor: dict[str, tuple[str, list[dict]]] = {}  # app 1's docs, for duplicates
        seeded_ids: list[int] = []

        for item in plan:
            app_id = _seed_application(
                db, rng, item, today, future_expiry, past_expiry, donor
            )
            seeded_ids.append(app_id)
            db.refresh(db.get(Application, app_id))

        print("[seed] running the validation pipeline on all 30 applications ...")
        for n, app_id in enumerate(seeded_ids, start=1):
            summary = pipeline.run_validation(app_id, actor="seed", animate=False)
            status = summary.get("gate_status", "ERROR")
            print(f"[seed]   {n:02d}/30 app #{app_id}: {status}"
                  f"{' (' + summary['error'][:60] + ')' if summary.get('error') else ''}")

        audit(db, "SEED_COMPLETE", actor="seed",
              detail={"applications": len(seeded_ids)})
        print("[seed] done - dashboard is ready")
        return True
    finally:
        db.close()


def _seed_application(db, rng, item, today, future_expiry, past_expiry,
                      donor: dict) -> int:
    idx = item["idx"]
    category = item["category"]
    reqs = rules_engine.category_rules(category)

    pool = INSTITUTION_NAMES[category]
    name = pool[((idx - 1) // 3) % len(pool)]
    city, state, pin_root, localities = CITIES[(idx - 1) % len(CITIES)]
    locality = localities[idx % len(localities)]
    pin = f"{pin_root}{(idx * 7) % 90 + 10:03d}"  # plausible PIN for the city
    address = f"{locality}, {city} - {pin}"
    aicte_id = f"AICTE-{state}{today.year - 1}-{idx * 37 % 90000 + 10000:05d}"
    intake = rng.choice(INTAKE_BY_CATEGORY[category])
    issue = (today - dt.timedelta(days=180 + idx)).strftime("%d-%m-%Y")

    app = Application(
        ref_no=f"EoA/2026/{idx:04d}",
        institution_name=name,
        category=category,
        aicte_id=aicte_id,
        address=address,
        approved_intake=intake,
        scenario=item["scenario"],
        status="UPLOADED",
        created_by="seed",
    )
    db.add(app)
    db.commit()

    db.add(
        MockRecord(
            aicte_id=aicte_id,
            institution_name=name,
            category=category,
            address=address,
            approved_intake=intake,
            status="APPROVED",
            valid_upto=future_expiry,
        )
    )
    db.commit()

    programme = {
        "Engineering": "B.E. / B.Tech (CSE, ECE, ME, CE) - 4 years",
        "Management": "MBA / MCA - 2 years",
        "Pharmacy": "B.Pharm - 4 years",
    }[category]

    upload_dir = config.UPLOAD_DIR / f"app_{app.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    seq_base = idx * 10
    for n, req in enumerate(reqs, start=1):
        doc_type = req["doc_type"]
        if item["kind"] == "missing" and doc_type == item.get("missing"):
            continue  # scenario B (and the other 'missing' apps)

        portal = req.get("issuer_portal") or ""
        seq = seq_base + n
        doc_number = f"{DOC_PREFIX.get(doc_type, 'DOC')}/{state}/{today.year}/{seq:04d}"
        qr = f"VG{seq:06d}"
        sig = signature_for(portal or "internal", doc_number, qr)

        ctx = {
            "name": name, "aicte_id": aicte_id, "address": address,
            "intake": intake, "programme": programme, "doc_number": doc_number,
            "qr": qr, "sig": sig, "issue": issue, "expiry": future_expiry,
            "authority": AUTHORITIES.get(portal, AUTHORITIES[""]),
            "altered_issue": (today - dt.timedelta(days=3)).strftime("%d-%m-%Y"),
        }

        # ---- duplicates (apps 28-30) reuse app 1's documents verbatim -------
        copied = False
        tamper_gt = None
        if item["kind"] == "duplicate" and doc_type in donor:
            src_path, src_tokens = donor[doc_type]
            stored = upload_dir / f"copy_{seq}_{Path(src_path).name}"
            shutil.copyfile(src_path, stored)
            tokens = src_tokens
            copied = True
        else:
            stored = upload_dir / f"{seq}_{doc_type.lower()}.pdf"
            tamper = bool(item.get("tamper")) and doc_type == "PREV_EOA_LETTER"
            degraded = bool(item.get("degraded")) and doc_type == "EOA_FORM"
            if item["kind"] == "expired" and doc_type == "FIRE_SAFETY_NOC":
                ctx["expiry"] = past_expiry
            if tamper:
                ctx["sig"] = "".join(
                    rng.choice("0123456789abcdef") for _ in range(48)
                )  # forged signature -> issuer says INVALID
            tokens, tamper_gt = build_document(
                stored, doc_type, req, ctx, tamper=tamper, degraded=degraded
            )

        doc = Document(
            application_id=app.id,
            doc_type=doc_type,
            filename=Path(stored).name,
            stored_path=str(stored),
            mime="application/pdf",
        )
        db.add(doc)
        db.commit()

        if not copied:
            gt = {"pages": [{"page_no": 1, "tokens": tokens}]}
            if tamper_gt:
                gt["tamper"] = tamper_gt
            (config.MOCK_OCR_DIR / f"doc_{doc.id}.json").write_text(
                json.dumps(gt), encoding="utf-8"
            )

        # ---- mock issuer-portal record --------------------------------------
        if portal and not copied:
            valid_upto = (
                past_expiry
                if item["kind"] == "expired" and doc_type == "FIRE_SAFETY_NOC"
                else future_expiry
            )
            rec = IssuerRecord(
                portal=portal,
                doc_number=doc_number,
                holder_name=name,
                qr_token=qr,
                signature=signature_for(portal, doc_number, qr),
                issue_date=issue,
                valid_upto=valid_upto,
            )
            if item.get("outage") and doc_type == "FIRE_SAFETY_NOC":
                rec.source_unavailable = True  # scenario D: pinned portal outage
            db.add(rec)
            db.commit()

        # donor material for the duplicate apps
        if idx == 1 and doc_type in ("PREV_EOA_LETTER", "FIRE_SAFETY_NOC"):
            donor[doc_type] = (str(stored), tokens)

    audit(
        db, "APP_CREATE", actor="seed", role="system",
        entity_type="application", entity_id=app.id,
        detail={"ref_no": app.ref_no, "category": category, "kind": item["kind"],
                "scenario": item["scenario"]},
    )
    return app.id
