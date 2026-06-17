# NILAM Backend — Design Spec

**Date:** 2026-06-17
**Status:** Approved for planning
**Companion:** `backend_info.md` (service-by-service API contracts — the source of truth for request/response shapes; this spec references it rather than duplicating every field).

---

## 1. Goal

Build a single new backend, `nilam_backend/`, that serves the NILAM KPR UI
(`nilam-prototype`). It owns the **decision/calculation + orchestration** layer
that runs in the browser today, **consumes** the existing OCR services and
normalizes their output to the UI's shapes, and exposes the assembled,
UI-shaped `ApplicationView` the dashboard renders.

The browser stops computing anything authoritative: it submits inputs, polls
orchestration events, and renders server-assembled views. *Frontend may preview;
the server decides.*

---

## 2. Decisions (locked during brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Scope | One new backend folder serving all 19 capabilities | User wants one cohesive backend |
| OCR/match services (1, 3, 4, 5, 15) | **Consume** over HTTP + normalize; do not build | Already implemented in `ocr_*`; re-deriving parsing is wasteful/risky |
| Identity (2) + SLIK (6) | **Fixture** now: real contracts, seeded data | No backend exists today; real KTP extraction / bureau feed deferred |
| Agunan-from-link (8) | **External / out of scope** | Done in another (future) service; `AgunanData` arrives as orchestration input |
| NPW (7) | **Consume** `house_fair_market_value` `/predict` | Already implemented |
| Calc/decision (9–14, 16–19) | **Build** (port from TS engines/lib/data) | This is the net-new value |
| Language / framework | **Python / FastAPI** | Matches existing services and `ocr_orchestrator`; one runtime |
| Layout | **Modular monolith** — one app, folder per service, shared `core/` | Single-applicant prototype; calc services are pure functions → in-process calls, not HTTP. Hybrid split documented as the future exit |
| Persistence | **In-memory async job store** (single worker) | Matches `ocr_orchestrator`; durability/audit deferred |
| Packaging / run | **Plain uvicorn** + `requirements.txt` + `.env`; no Docker yet | Fastest start; containerize later |
| Slip THR/bonus | **Source THR/bonus from mutasi credit classification**, not the slip | `ocr_slip` does not extract them; mutasi already classifies Gaji/THR/Bonus/Insentif |

**Future exit (documented, not built):** if one group (realistically OCR, or the
whole backend under load) needs independent scaling, extract that folder into its
own deployable — the "Hybrid (Option 3)" layout. Module boundaries are drawn so
this is a lift, not a rewrite.

---

## 3. Verification findings (why the adapter/projection layer exists)

The existing OCR output does **not** match the UI shapes natively. Confirmed by
reading each producer against the UI TypeScript contracts and the mapping layer:

- **`ocr_sk`** — ✅ matches (only snake→camel renames, already handled).
- **`ocr_classifier`** — ⚠️ classification matches; it does **not** return KTP
  fields (the UI's classify route assumes a same-pass `fields` that never comes).
- **`ocr_mutasi`** — ⚠️ returns `credits[]` not `transactions[]`; `keterangan`→
  `remark`, `amount`→`nominal`, `type` `"DB"/"CR"`→`dk` `"Debit"/"Kredit"`; missing
  `noRekening`, `count`, `totalKredit/totalDebet`, `gajiNominal`, `ringkasan`
  (category totals live in `audit`, not forwarded).
- **`ocr_slip`** — ❌ renames **plus** a real data gap: no separate `thr`/`bonus`
  (lumped into `tunjangan`), no `potonganBonus/Thr/Cuti`, and collapses to one
  aggregate record instead of per-month `records[]`.
- **`ocr_match`** — ❌ returns matched *pairs* + raw lists, not the UI's
  `MatchTxn[]`/`MonthlyRecap[]`; the monthly aggregation runs in the browser
  (`buildMatch`) today; naming diverges (`incentive` vs `bonus`, `deduction` vs
  `potongan`, `total_paid` vs `gajiSlip`); deduction not decomposed.
- **Identity (KTP/KK)** and **SLIK** — ❌ no backend at all; `/extract-ktp`,
  `/extract-kk`, `/slik` do not exist. The prototype only works via fixtures.

**Consequence:** the new backend owns (a) an **upstream normalizer** per producer
that renames/aggregates into the UI shapes, and (b) a **projection** layer that
builds the UI-shaped views and **owns the monthly-recap aggregation** (ported
`buildMatch`).

---

## 4. Architecture

Modular monolith. One FastAPI app mounts a router per service. Cross-service calls
are **in-process function calls**, not HTTP. Shared infra + upstream clients in
`core/`; shared contracts in `domain/`; UI-view assembly in `projection/`;
reference tables as data in `data/`.

```
nilam_backend/
├── app/
│   ├── main.py              # FastAPI: mounts routers, /health, /docs
│   └── settings.py          # env: upstream URLs, thresholds, rate-table version
├── core/                    # shared infra — no business logic
│   ├── envelope.py          # {ok:true|false} helpers + error types
│   ├── jobs.py              # in-memory async job store (ported from ocr_orchestrator)
│   ├── http.py              # async HTTP client (timeouts, retries)
│   ├── money.py             # IDR integer helpers
│   └── upstream/            # HTTP clients + field NORMALIZERS → UI shape
│       ├── classifier.py    #  ocr_classifier  → ClassifyResult
│       ├── slip.py          #  ocr_slip        → SlipRecord (rename; thr/bonus omitted)
│       ├── mutasi.py        #  ocr_mutasi      → MutasiExtract (credits→transactions,
│       │                    #                    keterangan→remark, amount→nominal,
│       │                    #                    DB/CR→Debit/Kredit, totals, ringkasan)
│       ├── sk.py            #  ocr_sk          → SkExtract (snake→camel)
│       ├── match.py         #  ocr_match       → match pairs
│       └── npw.py           #  house_fair_market_value /predict → NPW
├── domain/                  # shared Pydantic contracts = the UI shapes
│   ├── documents.py         # MutasiExtract, SlipRecord, KtpExtract, KkExtract,
│   │                        #   SkExtract, ClassifyResult
│   ├── income.py            # IncomeComponent, CustomerIncome, ThpResult
│   ├── agunan.py            # AgunanData, AgunanKlasifikasi
│   ├── slik.py              # SlikReport, SlikLoan
│   └── decision.py          # CreditScore, DecisionResult, OrchestrationEvent,
│                            #   ApplicationView
├── projection/              # raw upstream + service results → UI-shaped views
│   ├── matching.py          # PORT of buildMatch → MatchTxn[] + MonthlyRecap[]
│   └── application_view.py  # assemble the full ApplicationView (dashboard payload)
├── services/                # one folder per service: router · logic · models · tests
│   ├── identity/      # 2   FIXTURE (KTP/KK seeded, real contract)
│   ├── slik/          # 6   FIXTURE (seeded by NIK)
│   ├── income/        # 9   BUILD
│   ├── capacity/      # 10  BUILD
│   ├── plafond/       # 11  BUILD (LTV)
│   ├── offering/      # 12  BUILD
│   ├── credit_score/  # 13  BUILD
│   ├── fraud/         # 14  BUILD (stub → real later)
│   ├── coverage/      # 17  BUILD (validation)
│   ├── decision/      # 19  BUILD
│   ├── survey/        # 18  BUILD (uses core/jobs)
│   └── orchestration/ # 16  BUILD (drives pipeline; calls upstream/* + services/*;
│                      #            emits events; assembles ApplicationView)
├── data/
│   ├── kpr_rates.py         # KPR schemes + floating rate (versioned)
│   └── ltv_grid.py          # LTV matrix (baru/lama)
├── tests/                   # cross-service / integration
├── requirements.txt
├── .env.example
└── README.md
```

**Service folder shape (every one identical):**
`router.py` (FastAPI `APIRouter`) · `logic.py` (pure functions / ported engine —
the testable core) · `models.py` (request/response Pydantic) · `tests/`.

**Build scope summary:**

- **Build (calc/decision):** income (9), capacity (10), plafond (11),
  offering (12), credit_score (13), fraud (14), coverage (17), decision (19)
- **Build (flow):** orchestration (16), survey (18)
- **Fixture:** identity (2), slik (6)
- **Consume + adapt:** classifier (1), slip (3), mutasi (4), sk (5),
  match (15), npw (7)
- **External / out of scope:** agunan-from-link (8)

---

## 5. Data flow & orchestration

One async job per application, held in `core/jobs.py` (in-memory). The pipeline
node ids and order are the UI's existing ones:

```
upload → ocr → validasi → fraud → identity → slik → income → thp
   │       │       │         │        │         │       │       │
 job    upstream coverage  fraud   identity   slik    income  decision(19)
 init   classify  (17)     (14)    (2,fx)    (6,fx)  (9)+thp   + projection/
        +slip               via                       capacity application_view
        +mutasi            upstream                    (10)
        +sk                                            offering(12)
        +match(15)                                     plafond(11)+npw(7)
```

- `POST /applications/{id}/process` accepts `{ uploads, ocr?, userInput, agunan }`
  (`AgunanData` comes from the external from-link service or manual entry), creates
  a job, and runs the pipeline.
- Each node emits `OrchestrationEvent { node, status: running|success|error, at,
  detail? }`. The Processing screen polls `GET /applications/{id}/events` (polling
  first; SSE is a later option).
- `identity` runs only for joint/spouse income.
- `projection/matching.py` builds `MatchTxn[]` + `MonthlyRecap[]` server-side
  (replacing the browser `buildMatch`). THR/bonus are taken from mutasi
  classification; the slip supplies gross/pokok/potongan.
- On completion, `projection/application_view.py` assembles the `ApplicationView`
  served by `GET /applications/{id}`.
- **Survey (18)** is a separate human-in-the-loop call. For collateral priced
  ≥ `SURVEY_THRESHOLD` (Rp500.000.000) the flow waits at the survey step;
  `POST /applications/{id}/survey` with an approved value **overrides NPW** before
  the offer is computed.

---

## 6. Service contracts

All request/response shapes are specified in **`backend_info.md` §4** and are the
contract for implementation. Summary of what each built service does:

| # | Service | Endpoint | Responsibility |
|---|---|---|---|
| 9 | Income / THP | `POST /api/income/thp` | Components (Gaji/THR/Bonus/Insentif) + THP = Σ(value×weight) − angsuranSlik |
| 10 | Capacity (DIR) | `POST /api/capacity` | penghasilanBulanan, dirRate tiers (0.50/0.55/0.60), kemampuanBayar |
| 11 | Plafond (LTV) | `POST /api/agunan/plafond` | LTV grid → plafonAgunan, kebutuhan, penambahanDp |
| 12 | Offering | `POST /api/offering` | maxTenorByAge, per-scheme annuity schedules (fixed→floating) |
| 13 | Credit Scoring | `POST /api/credit-score` | 9-factor score (0–100) + grade + factors |
| 14 | Fraud | `POST /api/fraud` | per-check scores + overall (stub today) |
| 16 | Orchestration | `POST /api/applications/{id}/process`, `GET …/events`, `GET /api/applications/{id}` | drive pipeline, emit events, serve ApplicationView |
| 17 | Coverage / Validation | `POST /api/validation/coverage` | contiguous span + interior gaps; mutasi ≥ 12 months |
| 18 | Survey | `GET/POST /api/applications/{id}/survey` | RM gate; approved value overrides NPW |
| 19 | Decision | `POST /api/decision` | synthesize capacity + score + offering → approve/reject |
| 2 | Identity (fixture) | `POST /api/ocr/identitas` | KtpExtract / KkExtract from seeded data |
| 6 | SLIK (fixture) | `GET /api/slik` | SlikReport seeded by NIK |

Consumed (via `core/upstream/`, normalized to UI shape): classifier (1), slip (3),
mutasi (4), sk (5), match (15), npw (7).

Reference tables live in `data/` as versioned modules: `kpr_rates.py`
(schemes + 12.5% floating), `ltv_grid.py` (baru tier×prop×ukuran; lama
secondary/refinancing).

---

## 7. Conventions

- **Envelope:** `{ ok: true, ... }` on success; `{ ok: false, error: string,
  raw?: unknown }` on failure. Helpers in `core/envelope.py`.
- **Status codes:** `400` bad input, `422` unprocessable (locked/unrecognized
  PDF), `502` upstream unreachable/errored.
- **Upstream failures degrade, not 500:** a down OCR/NPW service is recorded in the
  job's `audit`/event `detail` and the pipeline continues with that stage marked
  `error`, mirroring `ocr_orchestrator` behavior; the `ApplicationView` still
  assembles with the missing piece null/empty (the UI already renders degraded).
- **Currency:** integers, IDR.
- **Money/precision:** rounding centralized in `core/money.py` to match the TS
  engines (avoid drift in annuity/THP).
- **Config:** upstream URLs and thresholds in `settings.py` from `.env`
  (`.env.example` committed). Default upstream ports must be reconciled with the
  real services (`ocr_classifier` 5001, `ocr_sk` 5002, `ocr_slip` 5003,
  `ocr_mutasi` 5004, `ocr_match` 5005, `house_fair_market_value` 8000) — see
  `backend_info.md` §3 reconciliation note.

---

## 8. Testing

- **pytest**, run from the new folder (mirrors `ocr_orchestrator/tests` style).
- **Per-service unit tests** target `logic.py` (pure functions) — the calc/decision
  services (9–14, 17, 19) are deterministic and get table-driven tests ported from
  the existing vitest cases (`thpEngine`, `creditScore`, `coverage`, `kpr`,
  `kemampuan`, matching) so parity with the TS engines is provable.
- **Upstream normalizers** tested against captured sample payloads (renames,
  DB/CR→Debit/Kredit, totals, ringkasan) — no live services needed.
- **Projection** tests assert UI-shaped output (MatchTxn/MonthlyRecap field names
  and the THR/bonus-from-mutasi rule).
- **Orchestration** tested with upstream calls patched (as `ocr_orchestrator` does)
  — verify event sequence, degraded-stage handling, and final ApplicationView.
- **Fixtures** (identity, slik) tested for contract shape.

---

## 9. Phased build order

1. **Skeleton:** `app/main.py`, `settings.py`, `core/envelope.py`, `core/money.py`,
   `core/jobs.py`, `/health`; one trivial service wired end-to-end.
2. **Pure calc (no I/O):** capacity (10), plafond (11) + `data/ltv_grid.py`,
   offering (12) + `data/kpr_rates.py`. Port vitest cases.
3. **OCR-shaped calc:** income/THP (9), coverage (17), and `projection/matching.py`
   (ported `buildMatch`). Depend only on already-defined shapes.
4. **Decision outputs:** credit_score (13), fraud (14 stub), decision (19).
5. **Fixtures:** identity (2), slik (6).
6. **Upstream layer:** `core/upstream/*` clients + normalizers; `upstream/npw.py`.
7. **Orchestration + assembly:** orchestration (16), `projection/application_view.py`,
   survey (18) + persistence in `core/jobs.py`.
8. **Wire the UI:** point `nilam-prototype` `/api/*` (or the BFF) at the new backend.

---

## 10. Out of scope (this iteration)

- Real KTP/KK extraction and a real SLIK bureau feed (fixtures stand in).
- Agunan-from-link (external/future service).
- Durable persistence / audit log (in-memory only).
- Docker/compose packaging.
- Splitting into independent microservices (the documented future exit).
- Re-implementing OCR parsing (consumed from existing `ocr_*`).
