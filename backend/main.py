"""VeriGate backend - FastAPI entrypoint.

    cd backend
    uvicorn main:app --reload --port 8000

MOCK_MODE=True (default) guarantees the demo never depends on heavy OCR/ML
installs; set MOCK_MODE=False to use real PaddleOCR/tesseract when available.
"""

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, models  # noqa: F401 (models registers the tables)
from app import seed as seed_module
from app.database import Base, engine
from app.mock_issuer_api import router as issuer_router
from app.routers import (
    applications,
    audit as audit_router,
    auth,
    insights,
    reviews,
)
from app.services import consistency, ocr

app = FastAPI(
    title="VeriGate API",
    version="1.0.0",
    description=(
        "AI decision-support for AICTE Extension of Approval validation. "
        "The Evidence Gate abstains when evidence is insufficient - "
        "humans make all final decisions."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # localhost demo only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(insights.router)
app.include_router(reviews.router)
app.include_router(audit_router.router)
app.include_router(issuer_router)


def _warmup():
    """Train the consistency model / probe OCR engines without blocking boot."""
    try:
        report = consistency.warmup()
        print(f"[startup] consistency engine: {report['engine']}")
    except Exception as exc:
        print(f"[startup] consistency warmup failed (heuristic will be used): {exc}")
    if not config.MOCK_MODE:
        try:
            report = ocr.engine_report()
            print(f"[startup] OCR engines: {report}")
        except Exception as exc:
            print(f"[startup] OCR probe failed: {exc}")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    print(f"[startup] MOCK_MODE={config.MOCK_MODE} db={config.DB_PATH}")
    if config.SEED_ON_STARTUP:
        # Seed in the background: on a 0.1-CPU cloud instance the full pipeline
        # takes minutes, and a blocking seed would fail the platform's startup
        # health check. Users are committed first, so login works right away
        # while the demo data fills in.
        threading.Thread(target=seed_module.seed_if_empty, daemon=True).start()
    threading.Thread(target=_warmup, daemon=True).start()


@app.get("/", include_in_schema=False)
def root():
    """Landing response for the bare API URL (otherwise FastAPI 404s here)."""
    return {
        "name": "VeriGate API",
        "version": "1.0.0",
        "status": "ok",
        "message": "VeriGate backend is running.",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
        "frontend": "https://verigate-app.vercel.app",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mock_mode": config.MOCK_MODE,
        "consistency": consistency.status(),
        "ocr": ocr.engine_report(),
    }
