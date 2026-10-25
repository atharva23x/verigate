# VeriGate backend image (optional - local dev needs no Docker)
FROM python:3.11-slim

WORKDIR /app

# CPU-only wheels: numpy/scipy/xgboost/pymupdf all ship manylinux wheels
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Seeds 30 synthetic applications on first boot (~30s), then serves the API
# Honors $PORT when set (Render/other PaaS), falls back to 8000 (docker compose)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
