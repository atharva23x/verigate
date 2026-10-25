# VeriGate — Demo Guide

What the prototype does, and what to look at in the recorded walkthrough.

| | |
|---|---|
| 🎬 **Demo video** | [Google Drive — `VeriGate Demo.mp4`](https://drive.google.com/file/d/1ok8D4ddMCRJCyEIHwnPq0eNAzhgTWuIm/view?usp=sharing) (anyone with the link, no sign-in) |
| 📱 **QR code** | [`demo-video-qr.png`](demo-video-qr.png) — points to the video |
| 🌐 **Live prototype** | https://verigate-app.vercel.app |
| 📄 **Full documentation** | [`SIH_Documentation.md`](SIH_Documentation.md) |

> The hosted demo runs on free tiers, so the first load can take a while while the
> backend wakes up. The recorded video is the authoritative walkthrough.

---

## Demo accounts

| Username | Password | Role | Rights |
|---|---|---|---|
| `officer1` | `officer123` | officer | create, upload, validate, decide |
| `reviewer1` | `reviewer123` | reviewer | approve / reject / request information |
| `auditor1` | `auditor123` | auditor | read-only; write endpoints return **403** |

---

## What the video shows

| Screen | What it demonstrates |
|---|---|
| **Login** | three role-based demo accounts |
| **Dashboard** | gate outcomes, `VERIFIED` vs `INSUFFICIENT_EVIDENCE`, risk-ranked application table, scenario badges A–E |
| **Scenario A** — app #1 | clean application → green **`EVIDENCE GATE: VERIFIED`**, zero flags |
| **Scenario B** — app #11 | missing Fire NOC → CRITICAL flag **`APH-MGT-003`**, checklist row *not uploaded*, gate abstains |
| **Scenario C** — app #24 | tampered date → **red ELA bounding box** over the edited region, issuer reports the signature invalid |
| **Scenario D** — app #5 | issuer portal down → **`SOURCE_UNAVAILABLE`** → manual review, never auto-rejected |
| **Scenario E** — app #6 | low OCR confidence → `INSUFFICIENT_EVIDENCE` → review queue |
| **Upload** | new application, live nine-step pipeline progress |
| **Review queue** | risk-ranked cases, approve / reject / request information with mandatory comment |
| **Audit log · Analytics · Report** | append-only trail, CSV export, A4 verification report with sign-off block |

The scenario order matches the seeded dataset:
**30 applications → 8 `VERIFIED` / 22 `INSUFFICIENT_EVIDENCE`.**

---

> The prototype uses **synthetic data only** — generated PDFs, mock AICTE master
> records and mock issuer portals. No real institutional data is present anywhere
> in this repository or in the hosted demo.
