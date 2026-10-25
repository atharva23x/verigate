# VeriGate — Demo Guide

Everything a reviewer needs to see the prototype in action: the recorded walkthrough,
the live deployment, and the exact scenarios to look at.

| | |
|---|---|
| 🎬 **Demo video** | [Google Drive — `VeriGate Demo.mp4`](https://drive.google.com/file/d/1ok8D4ddMCRJCyEIHwnPq0eNAzhgTWuIm/view?usp=sharing) (anyone with the link, no sign-in) |
| 📱 **QR code** | [`demo-video-qr.png`](demo-video-qr.png) — points to the video |
| 🌐 **Live prototype** | https://verigate-app.vercel.app |
| 🔌 **Live API** | https://verigate-api-8ejd.onrender.com · docs at [/docs](https://verigate-api-8ejd.onrender.com/docs) |
| 📄 **Full documentation** | [`SIH_Documentation.md`](SIH_Documentation.md) |

> The hosted demo runs on free tiers. The Render backend **sleeps after 15 minutes
> of inactivity**, so the first request may take ~40 s. After a restart the 30
> demo applications reseed in the background — if the dashboard looks empty, wait
> a minute and refresh. The recorded video is the authoritative walkthrough.

---

## Demo accounts

| Username | Password | Role | Rights |
|---|---|---|---|
| `officer1` | `officer123` | officer | create, upload, validate, decide |
| `reviewer1` | `reviewer123` | reviewer | approve / reject / request information |
| `auditor1` | `auditor123` | auditor | read-only; write endpoints return **403** |

---

## What the video shows, in order

| Step | Screen | What to look for | Rough time |
|---|---|---|---|
| 1 | Login | three role-based demo accounts | 0:00 |
| 2 | Dashboard | gate outcomes, `VERIFIED` vs `INSUFFICIENT_EVIDENCE`, risk-ranked table, scenario badges A–E | 0:20 |
| 3 | **Scenario A** — app #1 | clean application → green **`EVIDENCE GATE: VERIFIED`**, zero flags | 0:50 |
| 4 | **Scenario B** — app #11 | missing Fire NOC → CRITICAL flag **`APH-MGT-003`**, checklist row *not uploaded*, gate abstains | 1:20 |
| 5 | **Scenario C** — app #24 | tampered date → **red ELA bounding box** over the edited region, issuer reports signature invalid | 1:50 |
| 6 | **Scenario D** — app #5 | issuer portal down → **`SOURCE_UNAVAILABLE`** → manual review, never auto-rejected | 2:30 |
| 7 | **Scenario E** — app #6 | OCR confidence 0.87 < 0.90 → `INSUFFICIENT_EVIDENCE` → review queue | 2:55 |
| 8 | Upload | new application, live nine-step pipeline progress | 3:10 |
| 9 | Review queue | risk-ranked cases, approve / reject / request info with mandatory comment | 3:25 |
| 10 | Audit log + analytics + report | append-only trail, CSV export, A4 verification report with sign-off block | 3:45 |

Exact timings depend on the recording; the scenario order above matches the seeded
dataset (`30 apps → 8 VERIFIED / 22 INSUFFICIENT_EVIDENCE`).

---

## Run it locally (one command)

```powershell
docker compose up --build
```

Then open http://localhost:5173 and sign in as `officer1` / `officer123`.

Without Docker, from the repo root:

```powershell
# terminal 1
cd backend && py -3.12 -m venv venv && .\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# terminal 2
cd frontend && npm install && npm run dev
```

Full setup, architecture and API reference: [`DEPLOYMENT.md`](DEPLOYMENT.md) ·
[`../PROJECT_README.md`](../PROJECT_README.md).

---

> The prototype uses **synthetic data only** — generated PDFs, mock AICTE master
> records and mock issuer portals. No real institutional data is present anywhere
> in this repository or in the hosted demo.
