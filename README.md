# VeriGate

**AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification for AICTE Extension of Approval (EoA)**

> **AI advises. Evidence decides. Humans approve.**

Smart India Hackathon 2026 · Problem statement **SIH26261** · All India Council for Technical Education (AICTE), Ministry of Education

| | |
|---|---|
| 🌐 **Live prototype** | [**https://verigate-app.vercel.app**](https://verigate-app.vercel.app) — sign in with `officer1` / `officer123` |
| 🎬 **Demo video (~4 min)** | [Google Drive](https://drive.google.com/file/d/1ok8D4ddMCRJCyEIHwnPq0eNAzhgTWuIm/view?usp=sharing) · [walkthrough notes](docs/DEMO.md) |
| 📄 **Full documentation (16 sections)** | [**docs/SIH_Documentation.md**](docs/SIH_Documentation.md) |

> ⏱ The hosted demo runs on free tiers, so the first load can take ~40 s while the
> backend wakes up. The demo video is the fastest way to see the full flow.

---

## What it does

Institutions submit EoA applications with dozens of scanned certificates — Fire NOCs,
building stability certificates, land deeds, council registrations, previous approval
letters. VeriGate reads them and does the preliminary checking:

```
upload → OCR → APH 2024-27 checklist → issuer verification →
tamper/duplicate detection → cross-record consistency → EVIDENCE GATE → human review → audit
```

Every extracted field carries a **page number, bounding box and confidence**. Every
finding carries a **rule ID, reason, document, page and bbox** — so an officer can see
exactly where the machine looked.

## The Evidence Gate

VeriGate does not try to answer *"is this application valid?"*. It answers a narrower,
safer question: **"is the evidence strong enough to mark this application VERIFIED?"**

| # | Gate condition | Threshold |
|---|---|---|
| 1 | Mean OCR confidence | > 0.90 |
| 2 | Every issuer-backed document confirmed | all `VERIFIED` |
| 3 | Critical rule violations | 0 |
| 4 | Tamper score | < 0.30 |
| 5 | Duplicate documents | 0 |
| 6 | Cross-record consistency | ≥ 0.70 |

All six must hold. Otherwise the result is **`INSUFFICIENT_EVIDENCE`** and the case goes
to a human review queue with evidence-linked reasons. Confidence is reported as the
**weakest link**, not an average — one unverified Fire NOC cannot be hidden by eleven
strong signals.

**It never auto-rejects, never auto-approves, and never certifies on partial evidence.**

---

## Screenshots

| Dashboard — gate outcomes, risk-ranked cases | Scenario C — tamper bounding box |
|---|---|
| <img src="docs/screenshots/02-dashboard.jpg" width="100%"> | <img src="docs/screenshots/03-tamper-bbox.jpg" width="100%"> |
| **Manual review queue** | **Submitted values vs AICTE master record** |
| <img src="docs/screenshots/05-review-queue.jpg" width="100%"> | <img src="docs/screenshots/07-consistency-vs-master.jpg" width="100%"> |

More: [all 12 screenshots](docs/screenshots/) · embedded in the [documentation](docs/SIH_Documentation.md#113-screenshots-captured-from-the-running-prototype).

---

## The five demo scenarios

| # | Scenario | What to look for |
|---|---|---|
| **A** | Clean application | green **`EVIDENCE GATE: VERIFIED`**, zero flags |
| **B** | Missing mandatory Fire NOC | CRITICAL flag **`APH-MGT-003`**, checklist row *not uploaded*, gate abstains |
| **C** | Tampered date on the past EoA letter | **red ELA bounding box** over the edited region, issuer reports the signature invalid |
| **D** | Issuer portal down | **`SOURCE_UNAVAILABLE`** → manual review, never auto-rejected |
| **E** | Low OCR confidence (0.87 < 0.90) | `INSUFFICIENT_EVIDENCE` → review queue |

All data is synthetic: generated PDFs, mock AICTE master records, mock issuer portals.

## Demo accounts

| Username | Password | Role | Rights |
|---|---|---|---|
| `officer1` | `officer123` | officer | create, upload, validate, decide |
| `reviewer1` | `reviewer123` | reviewer | approve / reject / request information |
| `auditor1` | `auditor123` | auditor | read-only; writes return **403** |

---

## Tech stack

**Frontend** React 18 · TypeScript · Vite · Tailwind · Axios
**Backend** FastAPI · Python 3.12 · SQLAlchemy · SQLite (PostgreSQL-ready) · Pydantic · ReportLab
**Analysis** PyMuPDF · PaddleOCR/Tesseract · XGBoost consistency model · ELA tamper detection · pHash duplicates · HMAC-signed mock issuer APIs
**Auth** PBKDF2-SHA256 · JWT · role guards · append-only audit log

## Run it locally

```bash
docker compose up --build
```

Then open http://localhost:5173 and sign in as `officer1` / `officer123`.
First boot seeds 30 synthetic applications through the full pipeline (~30 s).

---

## Documentation

| Document | Contents |
|---|---|
| [**SIH Project Documentation**](docs/SIH_Documentation.md) | 16 sections: abstract, problem statement, proposed solution, objectives, existing vs proposed system, methodology, technology stack, architecture, implementation with screenshots, innovation, feasibility, outcomes, future scope, references |
| [**Demo guide**](docs/DEMO.md) | Video, demo accounts, scenario walkthrough, local run |
| [**Project README**](PROJECT_README.md) | Feature detail, API reference, data model, architecture |
| [**Deployment guide**](docs/DEPLOYMENT.md) | Docker, local dev, Render + Vercel, configuration, troubleshooting |
| [**Documentation index**](docs/README.md) | Quick links and project facts |

---

> **Scope note.** VeriGate is decision support, not an approval authority. It does not
> grant approval, reject an application, or establish forgery. All statutory scrutiny,
> inspection and final decisions remain with the competent AICTE authorities.
