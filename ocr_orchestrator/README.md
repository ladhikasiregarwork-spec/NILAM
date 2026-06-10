# OCR Orchestrator

Sixth sibling service (port **8500**). Accepts an unlabeled PDF bundle,
classifies each document via `ocr_classifier`, routes it to the right extractor
(`ocr_slip` / `ocr_mutasi` / `ocr_sk`), verifies salary slips against bank Gaji
credits by importing `ocr_match`'s matcher, and aggregates one **monthly
qualifying-income** figure. Async job + polling.

Scope is **orchestrator only** (single applicant v1). KTP/KK are classified but
not extracted; the applicant name is derived from slip → mutasi → sk. FMV, the
approve/reject decision, and frontend wiring are separate follow-ons. See the
design spec: `docs/superpowers/specs/2026-06-10-ocr-orchestrator-design.md`.

## Run (from the repo root)

```bash
.venv/Scripts/uvicorn ocr_orchestrator.api:app --host 0.0.0.0 --port 8500 --reload   # Windows
# ./ocr_orchestrator/run_api.sh --reload                                              # macOS/Linux
```

Needs the four upstream services running (or set `OCR_*_URL`). Or run everything
with `docker compose up --build`.

- Upload page: <http://localhost:8500/upload>
- Swagger: <http://localhost:8500/docs>

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/v1/applications` | multipart `files` (+ `bonus_accept_pct`, `password`) | `202` `{job_id, status, status_url}` |
| GET | `/api/v1/applications/{job_id}` | — | job status + `result` when complete |
| GET | `/health` | — | `{status, version}` |

```bash
curl -s -F "files=@ktp.pdf" -F "files=@slip.pdf" -F "files=@mutasi.pdf" \
  -F "bonus_accept_pct=0.5" http://localhost:8500/api/v1/applications
# {"job_id":"…","status":"pending","status_url":"/api/v1/applications/…"}
curl -s http://localhost:8500/api/v1/applications/<job_id> | python -m json.tool
```

## Limitations (v1)

- In-memory job store: **single uvicorn worker only**; jobs lost on restart.
- No persistence, no auth, no rate limiting — run behind an internal gateway.
