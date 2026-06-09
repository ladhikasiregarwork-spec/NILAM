# OCR Orchestrator — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design); pending implementation plan
**Scope:** Orchestrator only (one of several NILAM sub-projects)

---

## 1. Purpose

NILAM (New Intelligent Loan Application Management) ingests a customer's KPR
(mortgage) document bundle and, ultimately, returns an instant approval
decision. The five existing OCR services each handle one document type as a
standalone HTTP API. **Nothing ties them together today.**

This spec defines a new **`ocr_orchestrator`** service that assembles the
existing services into one flow:

> A caller uploads an unlabeled pile of PDFs. The orchestrator classifies each
> document, routes it to the correct extraction service, reconciles salary
> slips against bank credits, and computes a single **monthly qualifying
> income** figure — returned alongside the full per-document extraction detail.

It is the spine the rest of NILAM hangs off. The fair-market-value engine, the
approve/reject decision, and the frontend wiring are **separate follow-on
specs** (see §10, Out of Scope).

---

## 2. What already exists (the pieces being orchestrated)

All are flat packages at the repo root, sharing `.env` / `.venv` /
`requirements.txt`, each exposing an HTTP API.

| Service | Port | Endpoint used | Produces |
|---|---|---|---|
| `ocr_classifier` | 8000 | `POST /classify-batch` | `document_type` ∈ `{ktp, kk, sk, slip, mutasi, unknown}` per file |
| `ocr_slip` | 8200 | `POST /parse` | per-slip `worker_name, institution_name, total_paid, pokok, incentive, deduction, period` |
| `ocr_mutasi` | 8300 | `POST /api/v1/mutations/extract-batch` | `credits[]` + `audit.category_totals` for Gaji / Insentif / THR / Bonus (each `count`/`sum`/`min`) |
| `ocr_sk` | 8100 | `POST /parse` | employment-letter summary |
| `ocr_match` | 8400 | `matcher` module (imported) | slip↔Gaji per-month pairs (X+1 payroll-lag aware) |

**Gaps that constrain this design:**
- `ktp` / `kk` are recognized by the classifier but **not extracted in v1**.
  An existing KTP service (name / birth_date / nik) will be plugged in later;
  for now the applicant **name** is derived from the other documents (§6/§7).
  KK is recorded as a legality-upload flag (spouse verification is a later
  development).
- No fair-market-value service and no decision engine exist — out of scope.

---

## 3. Key decisions (from brainstorming)

1. **Scope: orchestrator only** — upload → classify → route → extract →
   aggregate income. FMV / decision / frontend are follow-ons.
2. **Income is derived into one figure** (not just raw passthrough), with the
   **bank statement and `ocr_match`-verified amounts as the source of truth**;
   slip-claimed numbers are a secondary fallback.
3. **Income components:** base + recurring allowances, with THR spread monthly
   and Bonus gated by an analyst percentage (see §6 for the exact formula).
4. **Single applicant** in v1 (no nasabah + pasangan joint income yet).
5. **Async job + polling** response model (a full bundle can take 60–90s).
6. **Integration style = Approach B:** HTTP-call the four OCR/extraction
   services once each; **import** `ocr_match`'s pure matcher rather than calling
   it over HTTP, to avoid re-parsing the slip and mutasi PDFs a second time
   (the mutasi LLM parse alone is ~29s).
7. **Identity docs:** `ktp` / `kk` are not extracted in v1. The applicant
   **name** is resolved from the already-extracted documents (slip → mutasi →
   sk). KTP's `birth_date` / `age` / `nik` are reserved `null` fields a
   follow-on fills by plugging in the existing KTP service; `kk` is recorded as
   a legality-upload flag and will drive spouse verification in a later
   development.

---

## 4. Service shape

New package **`ocr_orchestrator/`** at the repo root, port **8500**, following
the existing monorepo conventions: shared `.env` / `.venv` /
`requirements.txt`, a `run_api.sh`, a `Dockerfile`, and an entry in
`docker-compose.yml` with `depends_on: [ocr_classifier, ocr_slip, ocr_mutasi,
ocr_sk]` and upstream URLs injected via environment. Because it imports
`ocr_match.matcher`, the orchestrator image must contain the `ocr_match`
package (it does — the compose build context is the repo root).

### Modules

| File | Responsibility |
|---|---|
| `api.py` | FastAPI app: the two endpoints + `/health` + `/upload` test page + `/` redirect |
| `upstream.py` | async `httpx` clients for the four OCR services (one call each) |
| `pipeline.py` | the five-stage runner: classify → route → extract → verify → aggregate |
| `income.py` | pure income-aggregation logic (the one business rule) |
| `jobs.py` | in-memory async job store |
| `models.py` | Pydantic request / response / job types |
| `config.py` | `pydantic-settings`, reads the repo-root `.env` |
| `__init__.py` | version |

### Config (repo-root `.env`)

Reuses the existing `OCR_CLASSIFIER_URL`, `OCR_SLIP_URL`, `OCR_MUTASI_URL`,
`OCR_SK_URL` registry keys already in `.env.example`. Adds orchestrator-specific
tunables (defaults shown):

```
APP_PORT=8500
UPSTREAM_TIMEOUT_S=180          # generous — covers the slow mutasi batch parse
MAX_FILES=50                    # per-upload cap across all PDFs
DEFAULT_BONUS_ACCEPT_PCT=0.0    # conservative: bonus excluded until an analyst opts in
JOB_RETENTION=200               # most-recent jobs kept in memory (cap to bound growth)
```

---

## 5. API contract (async job + polling)

### `POST /api/v1/applications`

`multipart/form-data`:

| field | type | notes |
|---|---|---|
| `files` | repeated PDF | the unlabeled document pile (≥1) |
| `bonus_accept_pct` | form float, optional | `0.0`–`1.0`, default `DEFAULT_BONUS_ACCEPT_PCT`; clamped to range |
| `password` | form string, optional | passed through to extractors for protected PDFs |

Validated **synchronously** (≥1 file, ≤`MAX_FILES`, PDF content-type, per-file
size). On success: creates a job, schedules an async background task, returns
**`202 Accepted`**:

```jsonc
{ "job_id": "…", "status": "pending", "status_url": "/api/v1/applications/…" }
```

Validation failures → `400` (no files / wrong type) or `413` (too many / too
large), and **no job is created**.

### `GET /api/v1/applications/{job_id}`

Returns the job. `404` if unknown.

```jsonc
{
  "job_id": "…",
  "status": "pending | running | completed | failed",
  "stages": [
    { "name": "classify",  "status": "completed", "error": null },
    { "name": "extract",   "status": "running",   "error": null },
    { "name": "verify",    "status": "pending",   "error": null },
    { "name": "aggregate", "status": "pending",   "error": null }
  ],
  "result": null,        // populated only when status == "completed"
  "error": null          // populated only when status == "failed"
}
```

### Other routes

- `GET /health` → `{ status, version }`
- `GET /upload` → minimal self-contained HTML test page (parity with sibling services)
- `GET /` → `307` redirect to `/upload`

### Job store

In-memory dict guarded by an `asyncio.Lock`; the background task is an
`asyncio` task mutating the job as stages complete. Capped at `JOB_RETENTION`
most-recent entries.

**v1 limitations (documented, accepted for a prototype):**
- **Single uvicorn worker only** — do not run `--workers >1` (the store is
  per-process).
- **Jobs are lost on restart** — no persistence, matching the other services.

---

## 6. Pipeline & data flow

The background task runs five stages, updating `job.stages[]` as it progresses.

### Stage 1 — Classify
`POST` all files to `ocr_classifier` `/classify-batch`. Bucket by
`document_type`:

```
slips[]   mutasi[]   sk[]   ktp[]   kk[]   unknown[]
```

### Stage 2 — Extract (the three extractor calls run concurrently, once each)
- `slips[]` → `ocr_slip` `/parse`
- `mutasi[]` → `ocr_mutasi` `/api/v1/mutations/extract-batch`
- `sk[]` → `ocr_sk` `/parse`
- `ktp[]` → **not extracted in v1**; recorded as `recognized_not_extracted`. The
  applicant name is resolved from the other documents in Stage 5; the existing
  KTP service (name / birth_date / nik) is a follow-on plug-in.
- `kk[]` → **not extracted in v1**; recorded as `recognized_not_extracted`. Its
  presence satisfies the legality-upload requirement (visible in `documents[]`);
  KK-based spouse verification is a later development.
- `unknown[]` → recorded with a warning (possible mis-upload)

### Stage 3 — Verify
Import `ocr_match.matcher`. Build `ParsedSlip[]` from the Stage-2 slip results
and collect the Gaji credits (mutasi credits where `category == "Gaji"`). Feed
both to the matcher → slip↔Gaji per-month pairs. **No re-parsing, no HTTP hop.**
This is the verification signal driving the income trust hierarchy.

### Stage 4 — Aggregate income
`income.py` (§7).

### Stage 5 — Assemble (finalization)
Builds the result object below. Instantaneous — not a separately tracked entry
in `stages[]` (which tracks the four meaningful stages: classify, extract,
verify, aggregate); assembly is the job's completion step.
```jsonc
{
  "documents": [
    { "filename": "…", "document_type": "mutasi", "confidence": "high",
      "status": "extracted | recognized_not_extracted | unclassified",
      "extracted": { /* the service's own output for this doc, or null */ } }
    // one entry per uploaded file
  ],
  "applicant": {
    "name": "BUDI SANTOSO",   // resolved from available docs (precedence below)
    "name_source": "slip",    // "slip" | "mutasi" | "sk" | null
    "birth_date": null,       // reserved — KTP service fills this (follow-on)
    "age": null,              // reserved — derived from birth_date
    "nik": null               // reserved — KTP service fills this (follow-on)
  },
  "income": { /* §7 breakdown */ },
  "verification": { "matched_pairs": [ /* from ocr_match */ ], "verified_month_count": 12 },
  "audit": {
    "stage_timings_ms": { "classify": 0, "extract": 0, "verify": 0, "aggregate": 0 },
    "classifier_errors": [],
    "extractor_errors": [],
    "warnings": []
  }
}
```

The response keeps **both** the per-document extraction detail and the rolled-up
income — nothing the services produced is discarded.

**Applicant name resolution:** `name` is taken from the first available of slip
`worker_name` → mutasi account `nama` → sk worker name (KTP would rank highest
once its service is wired). `name_source` records which one fired; `name` is
`null` with a warning if none is available. `birth_date` / `age` / `nik` stay
`null` in v1.

---

## 7. Income computation (`income.py`)

Pure function. Inputs: mutasi `category_totals` + per-credit data, the
Stage-3 match result, and `bonus_accept_pct`. Output: the income breakdown.

### Formula

```
n_months = count of distinct YYYY-MM buckets containing any Gaji or Insentif credit
avg_monthly_gaji_insentif = total(Gaji + Insentif credits) / n_months
monthly_thr   = total(THR) / 12
bonus_monthly = total(Bonus) × bonus_accept_pct / 12

monthly_qualifying_income = avg_monthly_gaji_insentif + monthly_thr + bonus_monthly
```

### Trust hierarchy → `basis`

| `basis` | Condition | Behaviour |
|---|---|---|
| `bank_verified` | Mutasi present **and** ≥1 Gaji month confirmed by an `ocr_match` pair | Full formula; highest confidence |
| `bank_unverified` | Mutasi present, no slip match | Full formula; flagged "not slip-verified" |
| `slip_fallback` | No mutasi, but ≥1 slip exists | `monthly_qualifying_income = average(slip.total_paid across slips)`; unverified, low confidence; THR/Bonus unknown → 0 |
| `none` | Neither mutasi nor slip | `monthly_qualifying_income = null` + warning |

### Returned breakdown

```jsonc
{
  "n_statement_months": 12,
  "avg_monthly_gaji_insentif": 10500000,
  "monthly_thr": 1916667,            // total_THR / 12
  "bonus_total": 44000000,           // raw — the slider applies the %
  "bonus_accept_pct": 0.0,           // echoed from the request
  "bonus_monthly": 0,                // bonus_total × pct / 12
  "monthly_qualifying_income": 12416667,
  "basis": "bank_verified",
  "verified_month_count": 12,
  "warnings": []
}
```

`bonus_total` is returned **raw** alongside the applied figure, so a downstream
analyst bonus slider recomputes the total client-side with zero re-OCR:
`income = avg_monthly_gaji_insentif + monthly_thr + bonus_total × pct / 12`.

### Edge assumptions (known limitations)

1. **`n_months` denominator** = distinct months that actually carry a
   Gaji/Insentif credit, not the calendar span — a skipped payroll month does
   not deflate the average. (`ocr_mutasi` independently surfaces month
   coverage/gaps.)
2. **`monthly_thr = total_THR / 12`** regardless of how many statement months
   were uploaded — THR is annual, always spread over 12. Cleanest with a full
   ~12-month upload; a short upload may under/over-count if a THR happens to
   fall inside or outside the window. Accepted as a known limitation rather than
   prorated.

---

## 8. Error handling

Fail loud only when truly blocked; otherwise degrade with warnings.

| Situation | Behaviour |
|---|---|
| Bad upload (no files / over `MAX_FILES` / non-PDF / too large) | Rejected **synchronously**, `400`/`413`, no job created |
| `ocr_classifier` unreachable / errors | **Job → `failed`** (nothing to route) |
| One extractor (slip/mutasi/sk) unreachable or errors | Job still **`completed`**; bucket skipped, logged in `audit.extractor_errors`; income `basis` adjusts (e.g. mutasi down + slip present → `slip_fallback`) |
| Per-file OCR/LLM hiccup inside a service | Isolated by that service's own `audit`; surfaced through, never sinks the job |
| `unknown` / `ktp` / `kk` docs | Recorded with status + warning; job continues |
| `bonus_accept_pct` out of range | Clamped to `[0.0, 1.0]` |

Every partial outcome is visible in `audit` (`classifier_errors`,
`extractor_errors`, `warnings`, `stage_timings_ms`).

---

## 9. Testing

Mirrors the repo's "test the pure logic" instinct.

- **`income.py`** — real unit tests (stdlib `unittest`, no new dependency):
  the trust hierarchy, THR/12, bonus-pct gating, the `n_months` denominator,
  and all four `basis` cases. This is the first Python test suite in the repo;
  justified because income is the one business rule.
- **Routing/grouping** — classifier-result → buckets, unit-tested.
- **`pipeline.py`** — tested with **mocked upstream clients** (monkeypatched
  `upstream.py`): the full classify→assemble flow over canned service
  responses, no network.
- **`jobs.py`** — state transitions (`pending → running → completed/failed`).
- **Smoke script** — manual, networked, a real bundle end-to-end (like
  `ocr_mutasi`'s inline smoke scripts).

---

## 10. Out of scope (each a future spec)

- Fair-market-value engine (no service or data source exists yet).
- Approve/reject decision logic. Note: the originally-stated rule
  "application amount < fair market value < income" mixes a loan principal, an
  asset price, and a monthly income flow; it must become real checks (e.g.
  loan-to-value on the collateral + an installment-to-income / DSR affordability
  check) when the decision engine is specced.
- Frontend wiring (`nilam-prototype` is fully mocked today).
- Joint applicant (nasabah + pasangan) income.
- KTP service integration (`name` / `birth_date` / `age` / `nik`) — v1 derives
  the applicant name from other documents and leaves the rest `null`.
- KK extraction and KK-based spouse verification.
- Persistence, auth, rate limiting, multi-worker job storage.

---

## 11. Success criteria

- A single `POST /api/v1/applications` with a mixed PDF bundle returns a
  `job_id`; polling yields a `completed` job whose `result` contains correct
  per-document classification + extraction and a `monthly_qualifying_income`
  with the right `basis`.
- The bank-verified path produces a figure matching the §7 formula on the
  existing `ocr_mutasi` sample data (12-month BRI: Gaji × 12, etc.).
- A bundle with a slip but no mutasi yields `basis: "slip_fallback"`; an empty
  bundle yields `basis: "none"` with `monthly_qualifying_income: null` — neither
  errors the job.
- `applicant.name` is populated from the available documents (slip → mutasi →
  sk), with `birth_date` / `age` / `nik` reserved as `null` for the KTP
  follow-on.
- A downed extractor degrades to a partial result with the failure in
  `audit.extractor_errors`, not a failed job.
