# VeriGate — AI Decision-Support for AICTE Extension of Approval (EoA)

> **Smart India Hackathon prototype**
> CPU-only · localhost · synthetic data · AI advises, humans decide.

VeriGate validates AICTE EoA applications end-to-end: upload → OCR → APH 2024-27
auto-checklist → cross-record consistency (XGBoost) → tamper/duplicate detection
(ELA + pHash) → issuer verification (mocked portals) → **Evidence Gate** →
explainable flags → **manual review queue** → audit log.

> **The Evidence Gate is the core safety property:**
> `confidence > 0.90 AND every issuer source verified → VERIFIED`,
> otherwise → `INSUFFICIENT_EVIDENCE`. The system **abstains instead of guessing**
> and routes the application to human reviewers. **AI advises; humans decide.**

- **CPU-only, localhost, synthetic data only.** No real institution data anywhere.
- Backend: `http://localhost:8000` (FastAPI + SQLite/SQLAlchemy)
- Frontend: `http://localhost:5173` (React + TypeScript + Vite + Tailwind + Lucide + Axios)

> 📄 **Full SIH submission document (16 sections, with screenshots):**
> [`docs/SIH_Documentation.md`](docs/SIH_Documentation.md) · [documentation index](docs/README.md)
> 🎬 **Demo video:** [Google Drive](https://drive.google.com/file/d/1ok8D4ddMCRJCyEIHwnPq0eNAzhgTWuIm/view?usp=sharing) · [what the demo shows](docs/DEMO.md)
> 🌐 **Live prototype:** https://verigate-app.vercel.app (`officer1` / `officer123`)

---

## Quick start (two terminals, no Docker required)

### 1. Backend — `http://localhost:8000`

```powershell
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

On first boot the server **seeds itself** (~30 s): 4 users, 30 synthetic
applications with generated PDFs, mock AICTE/issuer records, and runs the full
pipeline on all 30 so the dashboard is immediately alive.

> No venv yet? Create one first:
> `py -3.12 -m venv venv; .\venv\Scripts\pip install -r requirements.txt`

### 2. Frontend — `http://localhost:5173`

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and sign in with a demo account below.

### Health check

```powershell
curl http://localhost:8000/health
```

---

## Demo accounts

| Username     | Password      | Role                        | Name shown                | Can do                                      |
| ------------ | ------------- | --------------------------- | ------------------------- | ------------------------------------------- |
| `officer1`   | `officer123`  | officer                     | Atharva Bhangale          | Upload, validate, review decisions          |
| `reviewer1`  | `reviewer123` | reviewer                    | Nayan Khune (Review Officer) | Review decisions (approve/reject/request)   |
| `auditor1`   | `auditor123`  | auditor **(read-only)**     | Tejas Bagade (Auditor)    | View everything, export audit — write APIs return **403** |

## The 5 demo scenarios (all verified end-to-end)

| # | Scenario | App | What to look for |
|---|----------|-----|------------------|
| **A** | Clean application → **VERIFIED** | **#1** (`EoA/2026/0001`) | Green `EVIDENCE GATE: VERIFIED`, zero flags, gate confidence 0.84 |
| **B** | Missing mandatory document → flagged by **rule ID** | **#11** | CRITICAL flag **`APH-MGT-003`** (Fire NOC not uploaded), checklist row `not uploaded`, gate abstains |
| **C** | Tampered date → **ELA bounding box overlay** | **#24** | Select the *Previous EoA Letter* tab: **red box** over the pasted date stamp (rule `APH-GEN-T01`, bbox `[0.10, 0.28, 0.19, 0.02]`), toggle **ELA heatmap**, issuer says INVALID (forged signature) |
| **D** | Issuer portal down → **SOURCE_UNAVAILABLE**, *not blocked* | **#5** | WARN flag `APH-GEN-I01`, issuer badge `SOURCE UNAVAILABLE`, app is routed to review — **never auto-rejected** |
| **E** | Low OCR confidence → **INSUFFICIENT_EVIDENCE → review queue** | **#6** | OCR confidence 0.87 (< 0.90 threshold), WARN flag `APH-GEN-O01`, appears in the Manual Review Queue |

Expected state after seed: **30 apps → 8 VERIFIED / 22 INSUFFICIENT_EVIDENCE / 0 in review, queue = 22.**

### Suggested walkthrough

1. Log in as **officer1** → Dashboard: stat cards, Evidence Gate pass/fail chart,
   risk-ranked table (scenario badges **A–E**).
2. Open **app #1** (A) → green verdict. Open **app #24** (C) → click *Previous EoA
   Letter*, watch the red overlay, toggle the ELA heatmap, click *"show on document"*
   on the tamper flag — the box pulses.
3. Open **app #11** (B), **#5** (D), **#6** (E) → explainable flags with rule IDs,
   reasons, document/page/bbox, confidence bars, checklist.
4. **Upload** page → create an application, drop PDFs, watch live step-by-step
   pipeline progress.
5. Sign out → **reviewer1** → on any open flag: Approve / Reject / Request info
   (comment required for the trail) → status rolls up to IN_REVIEW/APPROVED/REJECTED.
6. Sign out → **auditor1** → Audit Log: filter by actor/action, **Export CSV**.
   Try an upload — you'll get a 403 (read-only).

---

## `MOCK_MODE` (demo safeguard)

`MOCK_MODE=True` is the **default** (`backend/app/config.py`, overridable via env):

- OCR uses seeded ground-truth tokens (boxes + confidences) instead of loading
  PaddleOCR/tesseract — **the demo never waits on or crashes from a heavy model**.
- Issuer portals are queried in-process (instant, outage simulated per record).
- Tamper ground truth is merged for scenario C so the red bbox is deterministic.
- XGBoost still runs for real (CPU, trained in <1 s at startup); if it cannot
  train, a deterministic weighted fallback is used — **nothing ever raises**.

Set `MOCK_MODE=False` to use real engines: install `pip install -r requirements-ocr.txt`
(PaddleOCR en+hi, or pytesseract + Tesseract binary). The engine chain degrades
gracefully: `ground truth → PaddleOCR → tesseract → embedded PDF text layer → blank`.
Every pipeline step is failure-isolated: an errored step is recorded in progress
and the gate abstains.

Other env vars: see `backend/.env.example`
(`SEED_ON_STARTUP`, `JWT_SECRET`, `OCR_CONFIDENCE_THRESHOLD`, `ISSUER_OUTAGE_PORTALS`…).

---

## Architecture

```
verigate/
├── backend/
│   ├── main.py                  # FastAPI entrypoint, startup seeding + XGBoost warmup
│   ├── requirements.txt         # core deps (CPU-only)
│   ├── requirements-ocr.txt     # OPTIONAL real OCR engines
│   └── app/
│       ├── config.py            # MOCK_MODE + thresholds (env-overridable)
│       ├── models.py            # SQLAlchemy models (swap SQLite→Postgres in one line)
│       ├── schemas.py           # Pydantic request/response schemas
│       ├── security.py          # PBKDF2 password hashes + JWT + role guards
│       ├── audit.py             # append-only audit helper
│       ├── rules.json           # APH 2024-27 checklist per category
│       ├── seed.py              # 30 synthetic apps (ReportLab PDFs + mock OCR GT)
│       ├── mock_issuer_api.py   # UGC/Fire/State/PCI portals, HMAC signatures, outages
│       ├── routers/             # auth, applications, reviews, audit
│       └── services/
│           ├── pipeline.py      # orchestrator: 9 steps, live progress, flags
│           ├── evidence_gate.py # ★ confidence > 0.90 AND issuer verified
│           ├── ocr.py           # engine chain w/ graceful fallback
│           ├── extraction.py    # fields + per-field bbox & confidence
│           ├── rules_engine.py  # checklist evaluation → explainable flags
│           ├── tamper.py        # ELA (flat-region) + pHash duplicate detection
│           ├── consistency.py   # XGBoost cross-record scorer (+ fallback)
│           └── issuer.py        # issuer client (in-process / HTTP)
└── frontend/
    ├── src/pages/               # Login, Dashboard, Upload, ApplicationDetail,
    │                            # ReviewQueue, AuditLog
    ├── src/components/          # ★ BBoxOverlay (absolute-positioned boxes),
    │                            # StatusBadge, ScoreBar, ProgressSteps, Layout
    └── scripts/e2e-smoke.mjs    # headless-Chrome UI test (25 checks)
```

### Key API endpoints

```
POST /auth/login                     JWT login (officer | reviewer | auditor)
POST /applications                   create (officer)
POST /applications/{id}/documents    multipart upload (officer)
POST /applications/{id}/validate     run pipeline (background, live progress)
DELETE /applications/{id}            officer-only: removes app + its files (audited)
GET  /applications                   filter: status, category, q (risk-ranked)
GET  /applications/{id}              detail: documents, flags, checklist, gate
GET  /applications/{id}/flags        explainable flags (rule, bbox, page, reason)
GET  /applications/{id}/documents/{doc_id}/pages/{n}.png   rendered page (auth)
GET  /applications/{id}/documents/{doc_id}/ela.png         ELA heatmap (auth)
POST /reviews/{flag_id}/decision     APPROVE | REJECT | REQUEST_INFO (comment)
GET  /reviews/queue                  manual review queue (risk-ranked)
GET  /audit-log                      filterable, append-only
GET  /audit-log/export               CSV download
GET  /dashboard/stats                counts + gate pass rate
GET  /mock-issuer/portals            portal status (toggle outages for demos)
Interactive docs: http://localhost:8000/docs
```

### Explainable flags

Every flag stores **document ID, page number, normalized bounding box, rule ID,
severity, reason and timestamp**. The Application Detail page draws them as
absolute-positioned boxes over the rendered page: **red = CRITICAL** (tamper,
expired, missing), **orange = WARN** (low OCR, issuer unavailable, consistency),
**blue = extracted field highlights**.

### Roles (DPDP-style)

`officer` uploads/validates/reviews **and may delete an application it no longer
needs** (two-step confirm on the dashboard row or the application page — removes
the row, its documents/flags/decisions and their files, then writes an
`APP_DELETE` audit entry; the audit log itself is never edited) · `reviewer`
decides · `auditor` read-only (every write endpoint — including DELETE — returns
403). All actions land in the **append-only audit
log** (there is deliberately no update/delete API for it).

---

## Tests

```powershell
# API-level scenario test (backend must be running)
cd backend ; .\venv\Scripts\python.exe test_scenarios.py

# role matrix (officer/reviewer/auditor/anonymous)
cd backend ; .\venv\Scripts\python.exe test_roles.py

# DELETE endpoint: role guards, ref_no uniqueness, file cleanup, audit trail
# (mutates the data - reseed afterwards, see "Reset / reseed")
cd backend ; .\venv\Scripts\python.exe test_delete.py

# UI end-to-end test in headless Chrome (both servers running)
cd frontend ; npm run test:e2e
```

Both suites assert all 5 demo scenarios (A–E), the bbox overlay, ELA toggle,
role guards, dashboard counts and audit CSV export.

### Screenshots for the SIH presentation

```powershell
# both servers running -> writes high-res PNGs (2x) into frontend\screenshots\
cd frontend ; node scripts\screenshots.mjs
```

Produces: `01-login` (demo accounts), `02-dashboard` (how-it-works + 5 scenarios),
`03-tamper-bbox` (red tamper box, scenario C), `03b-fields-overlay` (all
explainable field boxes), `04-verified-clean` (scenario A), `05-review-queue`,
`06-audit-log`.

---

## Optional: Docker

```powershell
docker compose up --build
# backend  -> http://localhost:8000
# frontend -> http://localhost:5173
```

Docker is a **bonus** — local development needs no Docker at all (commands above).

---

## Reset / reseed

Stop the backend, then:

```powershell
cd backend
Remove-Item verigate.db -ErrorAction SilentlyContinue
Remove-Item storage -Recurse -Force -ErrorAction SilentlyContinue
# restart uvicorn → auto-seeds 30 fresh applications
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Port 8000 already in use | `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess` |
| `esbuild` postinstall blocked by npm 11 | `npm approve-scripts esbuild` (or `npm install` again and approve) |
| Frontend can't reach API | Ensure uvicorn is on **8000**; override with `frontend\.env` → `VITE_API_URL=http://localhost:8000` |
| XGBoost/sklearn warning | `pip install scikit-learn` (heuristic fallback works meanwhile) |
| Real OCR wanted | `pip install -r requirements-ocr.txt` and set `MOCK_MODE=False` |
