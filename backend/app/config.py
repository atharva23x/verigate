"""VeriGate configuration. Everything is env-overridable; MOCK_MODE defaults to True
so a live demo can never crash because a heavy OCR/ML dependency failed to load."""

import os
from pathlib import Path


def _bool(name: str, default: str = "False") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
APP_DIR = BASE_DIR / "app"

STORAGE_DIR = Path(os.getenv("VERIGATE_STORAGE", str(BASE_DIR / "storage")))
UPLOAD_DIR = STORAGE_DIR / "uploads"
PAGE_DIR = STORAGE_DIR / "pages"
ELA_DIR = STORAGE_DIR / "ela"
MOCK_OCR_DIR = STORAGE_DIR / "mock_ocr"

DB_PATH = Path(os.getenv("VERIGATE_DB", str(BASE_DIR / "verigate.db")))

MOCK_MODE = _bool("MOCK_MODE", "True")
SEED_ON_STARTUP = _bool("SEED_ON_STARTUP", "True")

JWT_SECRET = os.getenv("JWT_SECRET", "verigate-demo-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "480"))

# The Evidence Gate core threshold (spec: OCR confidence > 0.90 is one of five
# AND-conditions; see services/evidence_gate.py for the full gate logic)
OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.90"))
TAMPER_SCORE_THRESHOLD = 0.30
CONSISTENCY_THRESHOLD = 0.70
PHASH_DUPLICATE_MAX_DISTANCE = 8  # hamming distance on 64-bit pHash

# Portals simulated as DOWN for demo scenario D (SOURCE_UNAVAILABLE)
ISSUER_OUTAGE_PORTALS = [
    p.strip()
    for p in os.getenv("ISSUER_OUTAGE_PORTALS", "").split(",")
    if p.strip()
]

for _d in (UPLOAD_DIR, PAGE_DIR, ELA_DIR, MOCK_OCR_DIR):
    _d.mkdir(parents=True, exist_ok=True)
