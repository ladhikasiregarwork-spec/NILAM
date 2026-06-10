# syntax=docker/dockerfile:1
# Build from the REPO ROOT:
#   docker build -f ocr_orchestrator/Dockerfile -t ocr_orchestrator .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Shared helper package, the imported matcher's package, and this service.
COPY ocr_common/ ./ocr_common/
COPY ocr_match/ ./ocr_match/
COPY ocr_orchestrator/ ./ocr_orchestrator/

# Orchestrator fans out to the four OCR services over HTTP — point it at them
# via OCR_*_URL at runtime (compose sets these to service DNS names).
EXPOSE 8500
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8500/health', timeout=3)" || exit 1

# Single worker: the in-memory job store is per-process.
CMD ["uvicorn", "ocr_orchestrator.api:app", "--host", "0.0.0.0", "--port", "8500"]
