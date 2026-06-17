# nilam_backend

Modular-monolith FastAPI backend serving the NILAM KPR UI (`nilam-prototype`).
Design: `docs/superpowers/specs/2026-06-17-nilam-backend-design.md`; API
contracts: `backend_info.md` §4.

One FastAPI app mounts one router per service folder. Each service is
`router.py` (HTTP) · `logic.py` (pure ported engine) · `models.py` (Pydantic) ·
`tests/`. Reference tables live in `data/`, shared contracts in `domain/`,
UI-view assembly in `projection/`, cross-cutting infra in `core/`.

## Run (from the repo root)

    python -m venv .venv
    .venv/Scripts/python -m pip install -r nilam_backend/requirements.txt   # Windows
    .venv/Scripts/python -m uvicorn nilam_backend.app.main:app --reload --port 8600

Swagger UI at http://127.0.0.1:8600/docs · health at /health.

## Test (from the repo root)

    .venv/Scripts/python -m pytest nilam_backend -v

## Endpoints

Authoritative calc/decision (ported from the prototype's TS engines/lib/data):

| # | Service | Route |
|---|---------|-------|
| 9  | Income / THP            | `POST /api/income/thp` |
| 10 | Payment Capacity (DIR)  | `POST /api/capacity` |
| 11 | Collateral Plafond (LTV)| `POST /api/agunan/plafond` |
| 12 | KPR Offering            | `POST /api/offering` |
| 13 | Credit Scoring          | `POST /api/credit-score` |
| 14 | Fraud Detection (stub)  | `POST /api/fraud` |
| 15 | Slip↔Mutasi Matching    | `POST /api/matching` |
| 17 | Document Coverage       | `POST /api/validation/coverage` |
| 19 | Final Decision          | `POST /api/decision` |

Flow + fixtures:

| # | Service | Route |
|---|---------|-------|
| 16 | Orchestration | `POST /api/applications/{id}/process` · `GET .../events` · `GET /api/applications/{id}` |
| 18 | RM Survey     | `GET` / `POST /api/applications/{id}/survey` |
| 2  | Identity (fixture) | `POST /api/ocr/identitas` |
| 6  | SLIK (fixture)     | `GET /api/slik?nik=…` |

Upstream consumers (HTTP clients + normalizers to the UI shapes) live in
`core/upstream/` (classifier, mutasi, slip, sk, match, npw) for the orchestrator
to call the existing `ocr_*` / `house_fair_market_value` services. Reconcile the
default upstream ports in `app/settings.py` with the real services before going
live (see `backend_info.md` §3).

## Notes / deferred (design §10)

- Identity (2) and SLIK (6) are **fixtures** with real contracts; real KTP/KK
  extraction and a real bureau feed are deferred.
- Orchestration runs the pipeline **synchronously in-process** and exposes it via
  the job API (events + ApplicationView); SSE and true async workers are a later
  option. The job store (`core/jobs.py`) is **in-memory / single-worker** — not
  durable, not yet an audit log.
- THR/bonus are sourced from the **mutasi credit classification**, not the slip
  (the slip service does not extract them).
