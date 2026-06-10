#!/usr/bin/env bash
set -euo pipefail
# Run ocr_orchestrator from the repo root (where the shared .venv and .env live)
# so the package imports resolve. Override HOST/PORT via env; pass extra uvicorn
# flags through, e.g.:  ./ocr_orchestrator/run_api.sh --reload
#
# NOTE: in-memory job store => run a SINGLE worker only (no --workers >1).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec "$ROOT/.venv/bin/uvicorn" ocr_orchestrator.api:app \
  --host "${HOST:-0.0.0.0}" --port "${PORT:-8500}" "$@"
