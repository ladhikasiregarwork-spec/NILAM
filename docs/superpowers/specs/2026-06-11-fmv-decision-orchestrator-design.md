# FMV + Decision Orchestrator — Design Spec

**Date:** 2026-06-11
**Status:** ✅ Implemented (shipped to `main`, 2026-06-11)
**Scope:** `ocr_orchestrator` only — the FMV and approve/reject follow-ons named
in `2026-06-10-ocr-orchestrator-design.md` §10

---

## 1. Purpose

The existing `ocr_orchestrator` ends at a single **monthly qualifying income**
figure (`income.py`, spec `2026-06-10` §7). The original orchestrator spec
explicitly deferred two follow-ons (§10): the **fair-market-value** of the
collateral and the **approve/reject decision**. Both are now buildable — the
`house_fair_market_value` service exists (commit `94d5346`) and exposes
`POST /predict`.

This spec extends the orchestrator with two new pipeline stages — **`fmv`** and
**`decide`** — that turn the income figure plus a collateral description and a
loan request into a credit **recommendation** (`eligible` /
`not_eligible` / `refer_to_analyst`) backed by a loan-to-value (LTV) check and a
debt-service-ratio (DSR) affordability check. The orchestrator **advises**; a
human Credit Analyst still makes the final call (matching the prototype's
`AnalystDecisionScreen`).

The originally-stated rule "application amount < fair market value < income"
(2026-06-10 §10) mixed a loan principal, an asset price, and a monthly income
flow. This spec replaces it with two real checks:

- **LTV** — `loan_amount / fair_value ≤ MAX_LTV` (collateral covers the loan).
- **DSR** — `monthly_installment / monthly_income ≤ MAX_DSR` (the applicant can
  afford the installment).

---

## 2. What already exists (the pieces being combined)

| Piece | Where | Produces |
|---|---|---|
| Orchestrator pipeline | `ocr_orchestrator/pipeline.py` | 5 stages classify→extract→verify→aggregate→assemble |
| Income rule | `ocr_orchestrator/income.py` | `IncomeBreakdown` with `monthly_qualifying_income` + trust `basis` |
| FMV service | `house_fair_market_value` (`POST /predict`) | `{land_value, building_value, fair_value, location_matched, backend, warnings}` |

**Constraints carried in from the codebase:**

- `house_fair_market_value` is a **standalone service** — its own
  `requirements.txt` / `.venv` / parquet lookup / models, deliberately **not**
  part of the shared OCR `.venv` / `.env` / `docker-compose` (per CLAUDE.md). It
  is therefore integrated **over HTTP**, like the other extractors — not imported
  in-process. (The in-process `ocr_match` import works only because it is pure
  stdlib and avoids re-parsing PDFs; FMV has neither property.)
- The FMV `linear` backend is **weak** (land test R² ≈ −0.27); `catboost` is the
  accurate one (R² ≈ 0.47–0.55). The decision surfaces FMV's own warnings rather
  than trusting the number blindly.
- **SLIK is not wired yet.** The applicant's *existing* monthly installment
  (needed for a complete DSR) comes from a separate service that is not ready.
  Until then the existing installment is a **hard-coded `0.0` placeholder**
  (`DEFAULT_EXISTING_INSTALLMENT`), structurally in place so wiring SLIK later is
  a one-value swap.

---

## 3. Key decisions (from brainstorming)

1. **Scope:** extend `ocr_orchestrator` with `fmv` + `decide` stages only. No new
   extractors, no frontend wiring, no SLIK service.
2. **Inputs = explicit form fields** on the existing
   `POST /api/v1/applications` (alongside the PDFs). No appraisal/application-form
   OCR is built; the analyst/applicant supplies collateral + loan terms directly.
3. **FMV integration = HTTP** (Approach A), preserving the standalone-service
   boundary and the orchestrator's existing upstream-client pattern.
4. **Decision output = recommendation + checks**, not a binary auto-decision: the
   orchestrator returns `eligible` / `not_eligible` / `refer_to_analyst` plus the
   LTV/DSR checks, computed values, and human-readable reasons. The analyst
   decides.
5. **Installment = annuity** computed from `{loan_amount, tenor_months,
   annual_interest_rate}` via the standard formula. Single fixed rate in v1 (no
   tiered fixed/floating).
6. **Existing installment = 0** placeholder until the SLIK service is ready.
7. **Conditional stages:** both new stages run only when their inputs are present;
   otherwise they are **`skipped`** and the job still returns income, mirroring
   the existing degrade-don't-fail philosophy.
8. **Decision honors the income trust hierarchy:** even when the math passes, a
   non-`bank_verified` income `basis` downgrades the recommendation to
   `refer_to_analyst`.

---

## 4. Pipeline & stages

The background task gains two stages between `aggregate` and assembly:

```
classify → extract → verify → aggregate → fmv → decide → (assemble)
```

`job.stages[]` now tracks six entries (classify, extract, verify, aggregate,
**fmv**, **decide**). `StageState` gains a new value **`skipped`** alongside
`pending|running|completed|failed`.

### Stage 5 — `fmv`
Runs only when collateral inputs are present. Calls `house_fair_market_value`
`POST /predict` once via a new `upstream.predict_fair_value()`
(`httpx.AsyncClient`, `FMV_URL`, `FMV_TIMEOUT_S`). Maps the JSON response to
`FmvResult`.
- Collateral absent → stage **`skipped`**, `fmv = None`, warning.
- Service unreachable / non-2xx → stage **`failed`**, `fmv = None`, logged in
  `audit.fmv_errors`; **job still completes**.

### Stage 6 — `decide`
Pure `decision.py` (no I/O). Runs only when the **loan** group is present;
otherwise stage **`skipped`**, `decision = None`. Inputs: the `IncomeBreakdown`
from Stage 4, the `FmvResult` from Stage 5 (or `None` if collateral was absent),
the parsed `LoanRequest`, and the configured thresholds. Produces
`DecisionResult` (§6).
- When it runs but FMV is absent/failed, or `income.basis == none` →
  recommendation **`refer_to_analyst`** with a reason (cannot fully assess);
  never `failed`.

### Assembly
`ApplicationResult` is extended with the four new optional fields; assembly stays
the job's instantaneous completion step (not a tracked stage).

---

## 5. API contract

### `POST /api/v1/applications` — new optional form fields

Added to the existing `multipart/form-data` (which keeps `files`,
`bonus_accept_pct`, `password`):

| Field | Type | Group | Notes |
|---|---|---|---|
| `luas_tanah` | float, `> 0` | collateral | land area m² |
| `luas_bangunan` | float, `≥ 0` | collateral | building area m² (`0` = land-only) |
| `kode_pos` | str, optional | collateral | postal code; lookup miss → FMV medians + warning |
| `kelurahan` | str, optional | collateral | standardized village/ward |
| `appraisal_month` | int `YYYYMM`, optional | collateral | passed through to FMV |
| `loan_amount` | float, `> 0` | loan | requested principal (plafond) |
| `tenor_months` | int, `> 0` | loan | loan term in months |
| `annual_interest_rate` | float, `≥ 0` | loan | decimal fraction, e.g. `0.105` |

**Presence rules:**
- Collateral group is considered present when **both** `luas_tanah` and
  `luas_bangunan` are supplied (`kode_pos`/`kelurahan`/`appraisal_month` optional).
  Present → run `fmv`.
- Loan group requires **all three** of `loan_amount`, `tenor_months`,
  `annual_interest_rate`. Present → run `decide` (which yields
  `refer_to_analyst` if FMV is absent/failed).
- Any group absent → its stage is `skipped`; the job still returns income.

**Validation (synchronous, before a job is created):** a *provided* field that
violates its constraint (e.g. `loan_amount ≤ 0`, `tenor_months ≤ 0`,
`annual_interest_rate < 0`, `luas_tanah ≤ 0`) → **`400`**, no job created.
A **partial** collateral or loan group (some but not all required fields) →
the group is treated as **not provided**, with a `warning` in `audit.warnings`
(lenient, consistent with the existing upload tolerance).

### `GET /api/v1/applications/{job_id}` — response additions

`stages[]` includes `fmv` and `decide` (each may be `skipped`). `result` gains
`collateral`, `loan`, `fmv`, `decision` (all `null` when not run). All existing
fields are unchanged.

---

## 6. Data models (`models.py`)

```jsonc
// echoed-back inputs
CollateralInput { luas_tanah, luas_bangunan, kode_pos?, kelurahan?, appraisal_month? }
LoanRequest     { loan_amount, tenor_months, annual_interest_rate }

// FMV service response (mirrors PredictResponse)
FmvResult { land_value, building_value, fair_value, location_matched, backend, warnings[] }

// one per check
CheckResult {
  name: "ltv" | "dsr",
  value: float,         // e.g. 0.72
  threshold: float,     // e.g. 0.80
  passed: bool,
  detail: string        // human-readable, e.g. "loan 720M / fair_value 1.0B = 72%"
}

DecisionResult {
  recommendation: "eligible" | "not_eligible" | "refer_to_analyst",
  monthly_installment: float | null,   // annuity result
  monthly_income: float | null,        // echoed monthly_qualifying_income used
  max_installment: float | null,       // MAX_DSR * income - existing_installment
  existing_installment: float,         // 0.0 placeholder (SLIK follow-on)
  ltv: CheckResult | null,
  dsr: CheckResult | null,
  reasons: string[],                   // why this recommendation
  warnings: string[]                   // FMV caveats, model-quality, etc.
}
```

`ApplicationResult` gains optional `collateral`, `loan`, `fmv`, `decision`.
`OrchestratorAudit` gains `fmv_errors: string[]`. `StageState` gains `"skipped"`.

---

## 7. Decision logic (`decision.py`)

Pure function. The orchestrator's **second** business rule (sibling of
`income.py`).

```
decide(income: IncomeBreakdown,
       fmv: FmvResult | None,
       loan: LoanRequest | None,
       *, max_ltv: float, max_dsr: float,
       existing_installment: float = 0.0) -> DecisionResult
```

### Monthly installment (annuity)

```
r = annual_interest_rate / 12
n = tenor_months
P = loan_amount
monthly_installment = P / n                      if r == 0
                    = P*r*(1+r)^n / ((1+r)^n - 1) otherwise
```

### Checks

```
# LTV — collateral covers the loan
ltv_value  = loan_amount / fair_value            (requires fair_value > 0)
ltv_passed = ltv_value <= max_ltv

# DSR — applicant can afford the installment
monthly_income  = income.monthly_qualifying_income
max_installment = max_dsr * monthly_income - existing_installment
dsr_value       = (monthly_installment + existing_installment) / monthly_income
dsr_passed      = dsr_value <= max_dsr
```

### Recommendation

| Condition | `recommendation` |
|---|---|
| LTV **and** DSR pass **and** `income.basis == bank_verified` | `eligible` |
| LTV **and** DSR pass, but `income.basis ∈ {bank_unverified, slip_fallback}` | `refer_to_analyst` (math OK, income not bank-verified) |
| LTV **or** DSR fails | `not_eligible` |
| `fmv is None` **or** `income.basis == none` (`monthly_qualifying_income` null) | `refer_to_analyst` (cannot fully assess) |

(`decide` is not invoked when the loan group is absent — that stage is `skipped`
and `decision` stays `null`; see §4/§5. The `loan is None` branch in the function
signature is a defensive guard only.)

`reasons[]` always explains the outcome (which checks passed/failed and the
income basis). FMV `warnings` and `location_matched == false` flow into
`decision.warnings` and are **surfaced, not auto-downgraded** — the analyst sees
the model-quality caveat and decides. `existing_installment` is echoed so the
DSR is auditable and the SLIK swap is obvious.

---

## 8. Error handling (extends 2026-06-10 §8)

| Situation | Behaviour |
|---|---|
| Collateral absent / partial | `fmv` **skipped**; warning; income-only result |
| Loan absent / partial | `decide` **skipped**, `decision = null`; warning (FMV still reported if collateral was given) |
| FMV service unreachable / errors | `fmv` stage **`failed`**, `audit.fmv_errors`; `decision → refer_to_analyst` (when loan supplied); **job completes** |
| `income.basis == none` | `decision → refer_to_analyst` (no income to assess) |
| `fair_value ≤ 0` from FMV | LTV check `passed = false` with detail; contributes to `not_eligible`/`refer` per matrix |
| Invalid *provided* loan/collateral value | **`400`** synchronously, no job created |
| `MAX_LTV` / `MAX_DSR` misconfigured | fall back to defaults `0.80` / `0.50` with a startup log |

Every partial outcome stays visible in `audit` (`fmv_errors`, `warnings`,
`stage_timings_ms` now includes `fmv` and `decide`).

---

## 9. Configuration (repo-root `.env`)

Adds to the orchestrator's existing keys:

```
FMV_URL=http://127.0.0.1:8000          # house_fair_market_value service
FMV_TIMEOUT_S=30                       # FMV /predict is fast (no LLM)
MAX_LTV=0.80                           # loan-to-value cap
MAX_DSR=0.50                           # debt-service-ratio cap (matches frontend InstallmentCard)
DEFAULT_EXISTING_INSTALLMENT=0.0       # placeholder until the SLIK service is wired
```

`config.py` (`pydantic-settings`) gains `fmv_url`, `fmv_timeout_s`, `max_ltv`,
`max_dsr`, `default_existing_installment`. For Docker, FMV would be added to
`docker-compose.yml` with the orchestrator gaining `depends_on: [..., house_fair_market_value]`
and `FMV_URL` injected (FMV builds from its own context/Dockerfile — a compose
follow-up, not required for local raw-uvicorn runs).

---

## 10. Testing

Mirrors the repo's "test the pure logic" instinct; extends the existing
`ocr_orchestrator/tests/` suite.

- **`decision.py` (new `test_decision.py`)** — the core unit suite:
  - annuity math incl. the `r == 0` branch (verified against a hand computation);
  - LTV pass/fail (incl. `fair_value ≤ 0`);
  - DSR pass/fail with `existing_installment = 0` and a non-zero sanity case;
  - the full recommendation matrix across all four income `basis` values;
  - missing `fmv` / missing `loan` / `basis == none` → `refer_to_analyst`.
- **FMV upstream client** — mocked `httpx`: success mapping to `FmvResult`, and
  service-down → error path feeding `audit.fmv_errors`.
- **`pipeline.py`** — extend the mocked-upstream tests: `fmv` + `decide` run on a
  full bundle; both `skipped` when inputs absent; `fmv`-down degrades to
  `refer_to_analyst` without failing the job.
- **`api.py`** — new form-field parsing; invalid provided loan/collateral → `400`;
  a `completed` job carries `fmv` + `decision`.

---

## 11. Out of scope (future specs)

- **Real SLIK existing-installment** — `existing_installment` stays the `0.0`
  placeholder; wiring the SLIK service replaces that one value.
- Joint applicant (nasabah + pasangan) affordability.
- Tiered fixed/floating interest schedules (v1 is single fixed-rate annuity).
- Appraisal-report / application-form OCR extraction (inputs stay manual form
  fields).
- Frontend wiring (`nilam-prototype` is fully mocked today).
- Persistence, auth, multi-worker job storage (inherited from 2026-06-10 §10).
- Switching the FMV backend to `catboost` for production accuracy (operational
  config, not orchestrator code).

---

## 12. Success criteria

- A `POST /api/v1/applications` with PDFs **plus** collateral + loan fields
  returns a `job_id`; polling yields a `completed` job whose `result.decision`
  carries a `recommendation`, both `ltv` and `dsr` `CheckResult`s, and a
  `monthly_installment` matching the §7 annuity formula.
- A bundle with **no** collateral/loan fields behaves exactly as today: `fmv` and
  `decide` are `skipped`, `decision` is `null`, income is unchanged.
- A bank-verified income with passing LTV + DSR → `eligible`; the same with
  `slip_fallback` income → `refer_to_analyst`.
- A loan that breaches either cap → `not_eligible` with the failing check named in
  `reasons`.
- FMV service down → job still `completed`, `decision.recommendation ==
  refer_to_analyst`, error in `audit.fmv_errors`.
- `decision.existing_installment == 0.0` and is echoed in the result, so the SLIK
  follow-on is a single-value change.
