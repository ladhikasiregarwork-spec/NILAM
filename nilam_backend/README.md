# nilam_backend

Modular-monolith FastAPI backend serving the NILAM KPR UI. See
`docs/superpowers/specs/2026-06-17-nilam-backend-design.md`.

## Run (from the repo root)

    python -m venv .venv
    .venv/Scripts/python -m pip install -r nilam_backend/requirements.txt   # Windows
    .venv/Scripts/python -m uvicorn nilam_backend.app.main:app --reload --port 8600

Swagger UI at http://127.0.0.1:8600/docs · health at /health.

## Test (from the repo root)

    .venv/Scripts/python -m pytest nilam_backend -v
