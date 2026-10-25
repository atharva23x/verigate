# VeriGate Documentation

This folder contains the project documentation for **VeriGate — AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification for AICTE Extension of Approval (EoA)**.

| Document | Description |
|---|---|
| [**SIH Project Documentation**](SIH_Documentation.md) | The complete 16-section submission document: abstract, problem statement, proposed solution, objectives, existing vs proposed system, methodology, technology stack, architecture, implementation, innovation, feasibility, outcomes, future scope and references. |
| [**Demo guide**](DEMO.md) | Demo video link, QR code, live deployment, demo accounts, scenario walkthrough with timecodes and local run instructions. |
| [**Deployment guide**](DEPLOYMENT.md) | Docker, local dev mode, Render + Vercel hosting, configuration and troubleshooting. |
| [**Screenshots**](screenshots/) | Captured from the running prototype: dashboard, tamper overlay, review queue, audit log, consistency view, duplicate pair, issuer portals and analytics. |
| [**Project README**](../PROJECT_README.md) | Feature detail, API reference, data model, architecture and setup. |
| [**Project overview**](../README.md) | Live prototype, demo video, screenshots, tech stack and documentation index. |

---

## Quick facts

| | |
|---|---|
| **Project** | VeriGate |
| **Problem statement** | SIH26261 — AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification |
| **Organisation** | All India Council for Technical Education (AICTE), Ministry of Education |
| **Theme / Category** | Smart Automation / Software |
| **Core principle** | The **Evidence Gate** abstains when evidence is weak: `VERIFIED` only when every evidence condition holds, otherwise `INSUFFICIENT_EVIDENCE` → human review. AI advises; humans decide. |
| **Prototype** | React + TypeScript + Vite frontend · FastAPI + SQLite backend · CPU-only · synthetic data |

---

> VeriGate is a decision-support prototype. It does not grant approval, reject an application, or establish forgery. All statutory scrutiny, inspection and final decisions remain with the competent AICTE authorities.
