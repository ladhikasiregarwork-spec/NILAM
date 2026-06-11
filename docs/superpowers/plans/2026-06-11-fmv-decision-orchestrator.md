# FMV + Decision Orchestrator Implementation Plan

> **Status — 2026-06-11: ✅ Implemented & shipped to `main` (tests passing).** The step checkboxes below are the original execution checklist, kept for history and not individually re-ticked (a few `(Optional)` manual/networked steps were not run).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ocr_orchestrator` with two new pipeline stages — `fmv` (HTTP call to the standalone `house_fair_market_value` service) and `decide` (a pure LTV + DSR credit-recommendation rule) — driven by new collateral + loan form fields, degrading gracefully when those inputs are absent.

**Architecture:** A new pure module `decision.py` (sibling of `income.py`) computes an annuity installment and an `eligible` / `not_eligible` / `refer_to_analyst` recommendation from the existing income figure, a fair-market-value, and a loan request. The orchestrator reaches FMV over HTTP (a thin client in `upstream.py`), preserving FMV's standalone-service boundary. Both new stages are conditional: they run only when their form-field inputs are present, else they are marked `skipped` and the job still returns income. SLIK existing-installment is a hard-coded `0.0` config placeholder.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2 / pydantic-settings, httpx (async), stdlib `unittest` + pytest runner.

**Spec:** `docs/superpowers/specs/2026-06-11-fmv-decision-orchestrator-design.md`

**Conventions (verified against the repo):**
- Run all tests from the **repo root**: `.venv/Scripts/python -m pytest ocr_orchestrator/tests -v` (Windows).
- Tests are stdlib `unittest`; async tests use `unittest.IsolatedAsyncioTestCase`; API tests use `fastapi.testclient.TestClient`; pipeline tests monkeypatch `pipeline.upstream`.
- All orchestrator modules are flat under `ocr_orchestrator/` and importable only from the repo root.
- Work on a feature branch (the execution skill handles branching). Commit after each task.

---

## Task 1: Config — FMV URL, timeouts, and decision thresholds

**Files:**
- Modify: `ocr_orchestrator/config.py` (add fields to `Settings`)
- Test: `ocr_orchestrator/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add this method inside `class TestSettings` in `ocr_orchestrator/tests/test_config.py`:

```python
    def test_fmv_and_decision_defaults(self):
        s = Settings(_env_file=None)
        self.assertEqual(s.fmv_url, "http://127.0.0.1:8000")
        self.assertEqual(s.fmv_timeout_s, 30.0)
        self.assertEqual(s.max_ltv, 0.80)
        self.assertEqual(s.max_dsr, 0.50)
        self.assertEqual(s.default_existing_installment, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_config.py::TestSettings::test_fmv_and_decision_defaults" -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'fmv_url'`

- [ ] **Step 3: Add the settings fields**

In `ocr_orchestrator/config.py`, insert these fields into `class Settings` immediately after the `job_retention` field (before `model_config`):

```python
    # Fair-market-value service (standalone; reached over HTTP, not imported —
    # it keeps its own .venv/parquet/models). Default = its uvicorn default port.
    fmv_url: str = "http://127.0.0.1:8000"
    fmv_timeout_s: float = 30.0

    # Decision thresholds.
    max_ltv: float = 0.80   # loan-to-value cap
    max_dsr: float = 0.50   # debt-service-ratio cap (matches the frontend InstallmentCard)
    # Existing monthly installment from SLIK — placeholder until that service is
    # wired. The DSR check subtracts this from the income capacity; 0.0 means
    # "assume no existing debt" for now.
    default_existing_installment: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_config.py -v`
Expected: PASS (all config tests)

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/config.py ocr_orchestrator/tests/test_config.py
git commit -m "feat(orchestrator): add FMV URL + LTV/DSR decision settings"
```

---

## Task 2: Models — new input/output types, `skipped` stage state, audit field

**Files:**
- Modify: `ocr_orchestrator/models.py`
- Test: `ocr_orchestrator/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add this method inside `class TestModels` in `ocr_orchestrator/tests/test_models.py`:

```python
    def test_decision_models_assemble(self):
        from ocr_orchestrator.models import (
            CheckResult, CollateralInput, DecisionResult, FmvResult, LoanRequest,
        )
        collateral = CollateralInput(luas_tanah=80.0, luas_bangunan=50.0)
        loan = LoanRequest(loan_amount=700_000_000, tenor_months=240,
                           annual_interest_rate=0.10)
        fmv = FmvResult(land_value=600_000_000, building_value=400_000_000,
                        fair_value=1_000_000_000, location_matched=True,
                        backend="linear", warnings=[])
        decision = DecisionResult(
            recommendation="eligible",
            ltv=CheckResult(name="ltv", value=0.70, threshold=0.80,
                            passed=True, detail="ok"),
        )
        self.assertIsNone(collateral.kode_pos)
        self.assertEqual(loan.tenor_months, 240)
        self.assertEqual(fmv.fair_value, 1_000_000_000)
        self.assertEqual(decision.recommendation, "eligible")
        self.assertEqual(decision.existing_installment, 0.0)
        self.assertIsNone(decision.dsr)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_models.py::TestModels::test_decision_models_assemble" -v`
Expected: FAIL with `ImportError: cannot import name 'CheckResult'`

- [ ] **Step 3: Add the models**

In `ocr_orchestrator/models.py`:

(a) Extend the `StageState` alias near the top:

```python
StageState = Literal["pending", "running", "completed", "failed", "skipped"]
```

(b) Add a new recommendation alias next to the other `Literal` aliases:

```python
DecisionRecommendation = Literal["eligible", "not_eligible", "refer_to_analyst"]
```

(c) Add these classes (place them after `IncomeBreakdown`):

```python
class CollateralInput(BaseModel):
    """Collateral description for the FMV call (echoed back in the result)."""
    luas_tanah: float
    luas_bangunan: float
    kode_pos: Optional[str] = None
    kelurahan: Optional[str] = None
    appraisal_month: Optional[int] = None


class LoanRequest(BaseModel):
    """The requested loan terms (echoed back in the result)."""
    loan_amount: float
    tenor_months: int
    annual_interest_rate: float   # decimal fraction, e.g. 0.105


class FmvResult(BaseModel):
    """house_fair_market_value /predict response."""
    land_value: float
    building_value: float
    fair_value: float
    location_matched: bool
    backend: str
    warnings: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    """One decision check (LTV or DSR). ``value`` is None when undefined."""
    name: str
    value: Optional[float] = None
    threshold: float
    passed: bool
    detail: str = ""


class DecisionResult(BaseModel):
    """The credit recommendation and the checks behind it."""
    recommendation: DecisionRecommendation
    monthly_installment: Optional[float] = None
    monthly_income: Optional[float] = None
    max_installment: Optional[float] = None
    existing_installment: float = 0.0
    ltv: Optional[CheckResult] = None
    dsr: Optional[CheckResult] = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

(d) Add `fmv_errors` to `OrchestratorAudit`:

```python
class OrchestratorAudit(BaseModel):
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
    classifier_errors: list[str] = Field(default_factory=list)
    extractor_errors: list[str] = Field(default_factory=list)
    fmv_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

(e) Extend `ApplicationResult` with the four new optional fields:

```python
class ApplicationResult(BaseModel):
    documents: list[DocumentResult]
    applicant: ApplicantInfo
    income: Optional[IncomeBreakdown]
    verification: VerificationInfo
    collateral: Optional[CollateralInput] = None
    loan: Optional[LoanRequest] = None
    fmv: Optional[FmvResult] = None
    decision: Optional[DecisionResult] = None
    audit: OrchestratorAudit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_models.py -v`
Expected: PASS (all model tests)

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/tests/test_models.py
git commit -m "feat(orchestrator): add collateral/loan/fmv/decision models + skipped stage"
```

---

## Task 3: Jobs — add `fmv` and `decide` to the default stage list

**Files:**
- Modify: `ocr_orchestrator/jobs.py:17` (the `_DEFAULT_STAGES` tuple)
- Test: `ocr_orchestrator/tests/test_jobs.py:11-12`

- [ ] **Step 1: Update the failing assertion**

In `ocr_orchestrator/tests/test_jobs.py`, change the assertion in `test_create_and_get` to expect the six stages:

```python
        self.assertEqual([s.name for s in job.stages],
                         ["classify", "extract", "verify", "aggregate", "fmv", "decide"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_jobs.py::TestJobStore::test_create_and_get" -v`
Expected: FAIL — actual list is `[classify, extract, verify, aggregate]`

- [ ] **Step 3: Extend `_DEFAULT_STAGES`**

In `ocr_orchestrator/jobs.py`, change line 17:

```python
_DEFAULT_STAGES = ("classify", "extract", "verify", "aggregate", "fmv", "decide")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_jobs.py -v`
Expected: PASS (all job-store tests)

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/jobs.py ocr_orchestrator/tests/test_jobs.py
git commit -m "feat(orchestrator): track fmv + decide stages in the job store"
```

---

## Task 4: `decision.py` — pure LTV/DSR recommendation rule

**Files:**
- Create: `ocr_orchestrator/decision.py`
- Create: `ocr_orchestrator/tests/test_decision.py`

- [ ] **Step 1: Write the failing tests**

Create `ocr_orchestrator/tests/test_decision.py`:

```python
import unittest

from ocr_orchestrator.decision import compute_installment, decide
from ocr_orchestrator.models import FmvResult, IncomeBreakdown, LoanRequest

THRESH = dict(max_ltv=0.80, max_dsr=0.50, existing_installment=0.0)


def _income(monthly, basis):
    return IncomeBreakdown(
        n_statement_months=12, avg_monthly_gaji_insentif=monthly or 0.0,
        monthly_thr=0.0, bonus_total=0.0, bonus_accept_pct=0.0, bonus_monthly=0.0,
        monthly_qualifying_income=monthly, basis=basis,
        verified_month_count=12, warnings=[],
    )


def _fmv(fair_value, location_matched=True, warnings=None):
    return FmvResult(land_value=fair_value, building_value=0.0,
                     fair_value=fair_value, location_matched=location_matched,
                     backend="linear", warnings=warnings or [])


def _loan(amount, tenor=240, rate=0.10):
    return LoanRequest(loan_amount=amount, tenor_months=tenor,
                       annual_interest_rate=rate)


class TestComputeInstallment(unittest.TestCase):
    def test_zero_rate_is_principal_over_tenor(self):
        m = compute_installment(LoanRequest(
            loan_amount=120_000_000, tenor_months=120, annual_interest_rate=0.0))
        self.assertEqual(m, 1_000_000)

    def test_annuity_matches_formula(self):
        loan = LoanRequest(loan_amount=100_000_000, tenor_months=12,
                           annual_interest_rate=0.12)
        r = 0.12 / 12
        n = 12
        expected = 100_000_000 * r * (1 + r) ** n / ((1 + r) ** n - 1)
        self.assertAlmostEqual(compute_installment(loan), expected, places=2)


class TestDecide(unittest.TestCase):
    def test_eligible_when_checks_pass_and_bank_verified(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertTrue(out.dsr.passed)
        self.assertEqual(out.recommendation, "eligible")
        self.assertEqual(out.existing_installment, 0.0)

    def test_refer_when_checks_pass_but_income_not_bank_verified(self):
        out = decide(income=_income(20_000_000, "slip_fallback"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertTrue(out.dsr.passed)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_not_eligible_when_ltv_exceeds_cap(self):
        # loan 450M / fair 500M = 0.90 > 0.80
        out = decide(income=_income(50_000_000, "bank_verified"),
                     fmv=_fmv(500_000_000), loan=_loan(450_000_000), **THRESH)
        self.assertFalse(out.ltv.passed)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_not_eligible_when_dsr_exceeds_cap(self):
        # tiny income -> installment dwarfs it
        out = decide(income=_income(2_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertFalse(out.dsr.passed)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_refer_when_no_fmv(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=None, loan=_loan(700_000_000), **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")
        self.assertIsNone(out.ltv)
        self.assertIsNone(out.dsr)

    def test_refer_when_no_loan(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=None, **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_refer_when_income_is_none(self):
        out = decide(income=_income(None, "none"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_zero_fair_value_fails_ltv(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(0.0), loan=_loan(700_000_000), **THRESH)
        self.assertFalse(out.ltv.passed)
        self.assertIsNone(out.ltv.value)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_fmv_warnings_flow_into_decision(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000, location_matched=False,
                              warnings=["medians fallback"]),
                     loan=_loan(700_000_000), **THRESH)
        self.assertIn("medians fallback", out.warnings)
        self.assertTrue(any("location not matched" in w.lower() for w in out.warnings))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_decision.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ocr_orchestrator.decision'`

- [ ] **Step 3: Write `decision.py`**

Create `ocr_orchestrator/decision.py`:

```python
"""Pure credit-decision logic (spec §7): combine income + FMV + loan into a
recommendation backed by LTV and DSR checks. The orchestrator's second business
rule, sibling of income.py. No I/O.

    monthly_installment = annuity(loan_amount, tenor_months, annual_interest_rate)
    LTV = loan_amount / fair_value                       <= max_ltv
    DSR = (installment + existing) / monthly_income      <= max_dsr
"""
from __future__ import annotations

from typing import Optional

from .models import CheckResult, DecisionResult, FmvResult, IncomeBreakdown, LoanRequest


def compute_installment(loan: LoanRequest) -> float:
    """Flat monthly installment via the standard annuity formula.

    r = annual_interest_rate / 12 ; n = tenor_months ; P = loan_amount.
    M = P*r*(1+r)^n / ((1+r)^n - 1), with the r == 0 -> P/n guard.
    """
    r = loan.annual_interest_rate / 12.0
    n = loan.tenor_months
    p = loan.loan_amount
    if r == 0:
        return p / n
    factor = (1.0 + r) ** n
    return p * r * factor / (factor - 1.0)


def decide(
    *,
    income: IncomeBreakdown,
    fmv: Optional[FmvResult],
    loan: Optional[LoanRequest],
    max_ltv: float,
    max_dsr: float,
    existing_installment: float = 0.0,
) -> DecisionResult:
    reasons: list[str] = []
    warnings: list[str] = []

    if fmv is not None:
        warnings.extend(fmv.warnings)
        if not fmv.location_matched:
            warnings.append(
                "FMV location not matched; fair_value fell back to training medians."
            )

    monthly_income = income.monthly_qualifying_income
    income_ok = monthly_income is not None and monthly_income > 0

    # Cannot fully assess -> refer.
    if loan is None or fmv is None or not income_ok:
        if loan is None:
            reasons.append("No loan request provided.")
        if fmv is None:
            reasons.append("No collateral / fair-market-value available.")
        if not income_ok:
            reasons.append("No positive qualifying income to assess affordability.")
        return DecisionResult(
            recommendation="refer_to_analyst",
            monthly_installment=None,
            monthly_income=monthly_income,
            max_installment=None,
            existing_installment=existing_installment,
            ltv=None,
            dsr=None,
            reasons=reasons,
            warnings=warnings,
        )

    installment = compute_installment(loan)

    # LTV — collateral covers the loan.
    fair_value = fmv.fair_value
    if fair_value > 0:
        ltv_value: Optional[float] = loan.loan_amount / fair_value
        ltv_passed = ltv_value <= max_ltv
        ltv_detail = (
            f"loan {loan.loan_amount:,.0f} / fair_value {fair_value:,.0f} "
            f"= {ltv_value:.1%} (cap {max_ltv:.0%})"
        )
    else:
        ltv_value = None
        ltv_passed = False
        ltv_detail = "fair_value is 0 or unknown; LTV cannot be satisfied."
    ltv = CheckResult(name="ltv", value=ltv_value, threshold=max_ltv,
                      passed=ltv_passed, detail=ltv_detail)

    # DSR — applicant can afford the installment.
    max_installment = max_dsr * monthly_income - existing_installment
    dsr_value = (installment + existing_installment) / monthly_income
    dsr_passed = dsr_value <= max_dsr
    dsr_detail = (
        f"installment {installment:,.0f} + existing {existing_installment:,.0f} "
        f"/ income {monthly_income:,.0f} = {dsr_value:.1%} (cap {max_dsr:.0%})"
    )
    dsr = CheckResult(name="dsr", value=dsr_value, threshold=max_dsr,
                      passed=dsr_passed, detail=dsr_detail)

    # Recommendation — math first, then the income trust hierarchy.
    if ltv_passed and dsr_passed:
        if income.basis == "bank_verified":
            recommendation = "eligible"
            reasons.append("LTV and DSR within limits; income is bank-verified.")
        else:
            recommendation = "refer_to_analyst"
            reasons.append(
                f"LTV and DSR within limits, but income basis is '{income.basis}' "
                "(not bank-verified)."
            )
    else:
        recommendation = "not_eligible"
        if not ltv_passed:
            reasons.append("LTV exceeds the cap." if ltv_value is None
                           else f"LTV {ltv_value:.1%} exceeds cap {max_ltv:.0%}.")
        if not dsr_passed:
            reasons.append(f"DSR {dsr_value:.1%} exceeds cap {max_dsr:.0%}.")

    return DecisionResult(
        recommendation=recommendation,
        monthly_installment=round(installment, 2),
        monthly_income=monthly_income,
        max_installment=round(max_installment, 2),
        existing_installment=existing_installment,
        ltv=ltv,
        dsr=dsr,
        reasons=reasons,
        warnings=warnings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_decision.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/decision.py ocr_orchestrator/tests/test_decision.py
git commit -m "feat(orchestrator): add pure LTV/DSR decision rule (decision.py)"
```

---

## Task 5: Upstream — `predict_fair_value()` FMV client

**Files:**
- Modify: `ocr_orchestrator/upstream.py` (add one async function)
- Create: `ocr_orchestrator/tests/test_upstream.py`

- [ ] **Step 1: Write the failing tests**

Create `ocr_orchestrator/tests/test_upstream.py`:

```python
import unittest
from unittest import mock

import httpx

from ocr_orchestrator import upstream


class _FakeResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    """Stand-in for httpx.AsyncClient as an async context manager."""
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None):
        if self._exc:
            raise self._exc
        return self._resp


def _patch_client(resp=None, exc=None):
    return mock.patch.object(upstream.httpx, "AsyncClient",
                             lambda *a, **k: _FakeClient(resp=resp, exc=exc))


class TestPredictFairValue(unittest.IsolatedAsyncioTestCase):
    async def test_success_returns_json(self):
        resp = _FakeResp(200, {"land_value": 600.0, "building_value": 400.0,
                               "fair_value": 1000.0, "location_matched": True,
                               "backend": "linear", "warnings": []})
        with _patch_client(resp=resp):
            out = await upstream.predict_fair_value(
                {"luas_tanah": 80, "luas_bangunan": 50})
        self.assertEqual(out["fair_value"], 1000.0)

    async def test_transport_error_raises_unreachable(self):
        with _patch_client(exc=httpx.ConnectError("refused")):
            with self.assertRaises(upstream.UpstreamUnreachableError):
                await upstream.predict_fair_value({"luas_tanah": 80, "luas_bangunan": 50})

    async def test_4xx_raises_http_error(self):
        with _patch_client(resp=_FakeResp(400, text="bad request")):
            with self.assertRaises(upstream.UpstreamHttpError):
                await upstream.predict_fair_value({"luas_tanah": 80, "luas_bangunan": 50})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_upstream.py -v`
Expected: FAIL with `AttributeError: module 'ocr_orchestrator.upstream' has no attribute 'predict_fair_value'`

- [ ] **Step 3: Add the FMV client**

Append to `ocr_orchestrator/upstream.py` (after `parse_sk`):

```python
async def predict_fair_value(collateral: dict[str, Any]) -> dict[str, Any]:
    """POST collateral to house_fair_market_value:/predict (JSON body, not
    multipart). Returns the FMV response dict: ``land_value``, ``building_value``,
    ``fair_value``, ``location_matched``, ``backend``, ``warnings``.

    Mirrors the error semantics of ``_post``: a transport/network error becomes
    ``UpstreamUnreachableError`` and a 4xx/5xx becomes ``UpstreamHttpError`` so
    the pipeline's fmv stage can degrade cleanly."""
    s = get_settings()
    url = f"{s.fmv_url}/predict"
    try:
        async with httpx.AsyncClient(timeout=s.fmv_timeout_s) as client:
            r = await client.post(url, json=collateral)
    except httpx.TransportError as exc:
        raise UpstreamUnreachableError(
            f"house_fair_market_value not reachable at {url}: {exc}"
        ) from exc
    if r.status_code >= 400:
        raise UpstreamHttpError("house_fair_market_value", r.status_code, r.text)
    return r.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_upstream.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/upstream.py ocr_orchestrator/tests/test_upstream.py
git commit -m "feat(orchestrator): add predict_fair_value FMV HTTP client"
```

---

## Task 6: Pipeline — run the `fmv` and `decide` stages

**Files:**
- Modify: `ocr_orchestrator/pipeline.py` (imports, `run_job`/`_execute` signatures, two new stage blocks, the result assembly)
- Test: `ocr_orchestrator/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add these methods inside `class TestRunJob` in `ocr_orchestrator/tests/test_pipeline.py` (it already imports `pipeline`, `JobStore`, `mock`, and defines `_async`/`_async_raise`):

```python
    async def _bank_verified_setup(self):
        from ocr_orchestrator.models import CollateralInput, LoanRequest
        files = [("mut.pdf", b"b")]
        classify = _async([
            {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        mutasi = _async({
            "files": [{"filename": "mut.pdf", "account": {"nama": "BUDI"}}],
            "credits": [{"source_file": "mut.pdf", "tanggal": "2025-03-25",
                         "keterangan": "GAJI", "amount": 20_000_000.0, "page": 1,
                         "category": "Gaji"}],
            "audit": {},
        })
        slips = _async([{"source_file": "mut.pdf", "worker_name": "BUDI",
                         "total_paid": 20_000_000.0, "period": "2025-03"}])
        sk = _async({"summary": {}})
        collateral = CollateralInput(luas_tanah=80.0, luas_bangunan=50.0)
        loan = LoanRequest(loan_amount=700_000_000, tenor_months=240,
                           annual_interest_rate=0.10)
        return files, classify, mutasi, slips, sk, collateral, loan

    async def test_fmv_and_decide_run_when_inputs_present(self):
        files, classify, mutasi, slips, sk, collateral, loan = \
            await self._bank_verified_setup()
        fmv = _async({"land_value": 600_000_000, "building_value": 400_000_000,
                      "fair_value": 1_000_000_000, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.fmv.fair_value, 1_000_000_000)
        self.assertEqual(job.result.decision.recommendation, "eligible")
        self.assertTrue(job.result.decision.ltv.passed)
        fmv_stage = next(s for s in job.stages if s.name == "fmv")
        decide_stage = next(s for s in job.stages if s.name == "decide")
        self.assertEqual(fmv_stage.status, "completed")
        self.assertEqual(decide_stage.status, "completed")

    async def test_stages_skipped_when_no_collateral_or_loan(self):
        files, classify, mutasi, slips, sk, _c, _l = await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.result.fmv)
        self.assertIsNone(job.result.decision)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "skipped")
        self.assertEqual(next(s for s in job.stages if s.name == "decide").status, "skipped")

    async def test_fmv_down_degrades_to_refer(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files, classify, mutasi, slips, sk, collateral, loan = \
            await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk), \
             mock.patch.object(pipeline.upstream, "predict_fair_value",
                               _async_raise(UpstreamUnreachableError("fmv down"))):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.result.fmv)
        self.assertEqual(job.result.decision.recommendation, "refer_to_analyst")
        self.assertTrue(job.result.audit.fmv_errors)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "failed")

    async def test_input_warnings_land_in_audit(self):
        files, classify, mutasi, slips, sk, _c, _l = await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, input_warnings=["partial loan ignored"])
        self.assertIn("partial loan ignored", job.result.audit.warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_pipeline.py::TestRunJob::test_fmv_and_decide_run_when_inputs_present" -v`
Expected: FAIL — `run_job()` got an unexpected keyword argument `collateral`

- [ ] **Step 3: Update imports in `pipeline.py`**

In `ocr_orchestrator/pipeline.py`, add two imports and extend the models import. After the existing `from .income import compute_income` line add:

```python
from .config import get_settings
from .decision import decide
```

Change the `from .models import (...)` block to:

```python
from .models import (
    ApplicantInfo,
    ApplicationResult,
    CollateralInput,
    FmvResult,
    LoanRequest,
    OrchestratorAudit,
    VerificationInfo,
)
```

- [ ] **Step 4: Extend `run_job` and `_execute` signatures**

Replace the `run_job` signature and its `_execute` call with:

```python
async def run_job(
    store: JobStore,
    job_id: str,
    files: list[tuple[str, bytes]],
    *,
    bonus_accept_pct: float,
    password: str | None,
    collateral: CollateralInput | None = None,
    loan: LoanRequest | None = None,
    input_warnings: list[str] | None = None,
) -> None:
    try:
        await _execute(
            store, job_id, files,
            bonus_accept_pct=bonus_accept_pct, password=password,
            collateral=collateral, loan=loan, input_warnings=input_warnings,
        )
    except Exception as exc:  # backstop — pipeline stages are mostly pure
        logger.exception("run_job crashed for job %s", job_id)
        await store.fail(job_id, f"internal error: {exc}")
```

Replace the `_execute` signature (keep its docstring/body, only the parameter list changes):

```python
async def _execute(
    store: JobStore,
    job_id: str,
    files: list[tuple[str, bytes]],
    *,
    bonus_accept_pct: float,
    password: str | None,
    collateral: CollateralInput | None = None,
    loan: LoanRequest | None = None,
    input_warnings: list[str] | None = None,
) -> None:
```

- [ ] **Step 5: Seed input warnings**

In `_execute`, immediately after the line `audit = OrchestratorAudit()`, add:

```python
    if input_warnings:
        audit.warnings.extend(input_warnings)
```

- [ ] **Step 6: Insert the two new stages**

In `_execute`, find the end of Stage 4 (the line `await store.set_stage(job_id, "aggregate", "completed")`). Immediately **after** it, insert:

```python
    # ---- Stage 5: fmv ------------------------------------------------------
    fmv_result: FmvResult | None = None
    if collateral is None:
        await store.set_stage(job_id, "fmv", "skipped")
        audit.warnings.append("No collateral provided; FMV skipped.")
    else:
        await store.set_stage(job_id, "fmv", "running")
        t0 = time.perf_counter()
        try:
            raw = await upstream.predict_fair_value(collateral.model_dump())
            fmv_result = FmvResult(**raw)
            await store.set_stage(job_id, "fmv", "completed")
        except Exception as exc:  # unreachable/http/bad-payload — degrade, don't fail
            logger.warning("fmv stage failed: %s", exc)
            audit.fmv_errors.append(f"house_fair_market_value: {exc}")
            await store.set_stage(job_id, "fmv", "failed", str(exc))
        timings["fmv"] = (time.perf_counter() - t0) * 1000

    # ---- Stage 6: decide ---------------------------------------------------
    decision_result = None
    if loan is None:
        await store.set_stage(job_id, "decide", "skipped")
        audit.warnings.append("No loan request provided; decision skipped.")
    else:
        await store.set_stage(job_id, "decide", "running")
        t0 = time.perf_counter()
        settings = get_settings()
        decision_result = decide(
            income=income,
            fmv=fmv_result,
            loan=loan,
            max_ltv=settings.max_ltv,
            max_dsr=settings.max_dsr,
            existing_installment=settings.default_existing_installment,
        )
        timings["decide"] = (time.perf_counter() - t0) * 1000
        await store.set_stage(job_id, "decide", "completed")
```

- [ ] **Step 7: Add the new fields to the assembled result**

In the Stage 5 assemble block, replace the `result = ApplicationResult(...)` construction with:

```python
    result = ApplicationResult(
        documents=doc_results,
        applicant=ApplicantInfo(name=name, name_source=name_source),
        income=income,
        verification=verification,
        collateral=collateral,
        loan=loan,
        fmv=fmv_result,
        decision=decision_result,
        audit=audit,
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_pipeline.py -v`
Expected: PASS (existing 4 tests + 4 new tests). The existing `test_happy_path_bank_verified` still passes because `collateral`/`loan` default to `None` (stages skip).

- [ ] **Step 9: Commit**

```bash
git add ocr_orchestrator/pipeline.py ocr_orchestrator/tests/test_pipeline.py
git commit -m "feat(orchestrator): run fmv + decide stages in the pipeline"
```

---

## Task 7: API — collateral + loan form fields, validation, wiring

**Files:**
- Modify: `ocr_orchestrator/api.py` (imports, helper functions, `create_application` params + body)
- Test: `ocr_orchestrator/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add these methods inside `class TestApi` in `ocr_orchestrator/tests/test_api.py`:

```python
    def test_invalid_loan_amount_is_400(self):
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"loan_amount": "-5"},
        )
        self.assertEqual(r.status_code, 400)

    def test_invalid_tenor_is_400(self):
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"tenor_months": "0"},
        )
        self.assertEqual(r.status_code, 400)

    def test_accepts_collateral_and_loan_fields_returns_202(self):
        classify = _async([
            {"filename": "x.pdf", "document_type": "unknown", "confidence": "low"},
        ])
        with mock.patch.object(self.api.upstream, "classify_documents", classify):
            r = self.client.post(
                "/api/v1/applications",
                files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
                data={
                    "luas_tanah": "80", "luas_bangunan": "50",
                    "kode_pos": "40123", "kelurahan": "antapani kidul",
                    "loan_amount": "700000000", "tenor_months": "240",
                    "annual_interest_rate": "0.105",
                },
            )
            self.assertEqual(r.status_code, 202)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_api.py::TestApi::test_invalid_loan_amount_is_400" -v`
Expected: FAIL — returns `202`, not `400` (the field is ignored as unknown form data today).

- [ ] **Step 3: Import the new models**

In `ocr_orchestrator/api.py`, change the models import line to:

```python
from .models import AcceptedResponse, CollateralInput, JobStatusResponse, LoanRequest
```

- [ ] **Step 4: Add the validation + builder helpers**

Add these module-level functions in `ocr_orchestrator/api.py` (place them just above the `create_application` function):

```python
def _validate_numeric(name: str, value: float | None, *, allow_zero: bool) -> None:
    """Reject a provided numeric field that violates its constraint."""
    if value is None:
        return
    if allow_zero and value < 0:
        raise HTTPException(status_code=400, detail=f"{name} must be >= 0.")
    if not allow_zero and value <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be > 0.")


def _build_collateral(luas_tanah, luas_bangunan, kode_pos, kelurahan,
                      appraisal_month, warnings: list[str]) -> CollateralInput | None:
    fields = (luas_tanah, luas_bangunan, kode_pos, kelurahan, appraisal_month)
    if luas_tanah is not None and luas_bangunan is not None:
        return CollateralInput(
            luas_tanah=luas_tanah, luas_bangunan=luas_bangunan,
            kode_pos=kode_pos, kelurahan=kelurahan, appraisal_month=appraisal_month,
        )
    if any(v is not None for v in fields):
        warnings.append("Partial collateral fields provided (need both luas_tanah "
                        "and luas_bangunan); FMV skipped.")
    return None


def _build_loan(loan_amount, tenor_months, annual_interest_rate,
                warnings: list[str]) -> LoanRequest | None:
    fields = (loan_amount, tenor_months, annual_interest_rate)
    if all(v is not None for v in fields):
        return LoanRequest(loan_amount=loan_amount, tenor_months=tenor_months,
                           annual_interest_rate=annual_interest_rate)
    if any(v is not None for v in fields):
        warnings.append("Partial loan fields provided (need loan_amount, "
                        "tenor_months and annual_interest_rate); decision skipped.")
    return None
```

- [ ] **Step 5: Add the form parameters**

In `create_application`, add these parameters after the existing `password` parameter (keep `password` as-is):

```python
    luas_tanah: Optional[float] = Form(None, description="Collateral land area m^2 (> 0)."),
    luas_bangunan: Optional[float] = Form(None, description="Collateral building area m^2 (>= 0)."),
    kode_pos: Optional[str] = Form(None, description="Collateral postal code."),
    kelurahan: Optional[str] = Form(None, description="Collateral village/ward."),
    appraisal_month: Optional[int] = Form(None, description="Appraisal month YYYYMM."),
    loan_amount: Optional[float] = Form(None, description="Requested loan principal (> 0)."),
    tenor_months: Optional[int] = Form(None, description="Loan term in months (> 0)."),
    annual_interest_rate: Optional[float] = Form(None, description="Annual rate as a decimal, e.g. 0.105 (>= 0)."),
```

- [ ] **Step 6: Validate, build, and pass through**

In `create_application`, immediately **before** the `job = await store.create()` line, insert:

```python
    _validate_numeric("luas_tanah", luas_tanah, allow_zero=False)
    _validate_numeric("luas_bangunan", luas_bangunan, allow_zero=True)
    _validate_numeric("loan_amount", loan_amount, allow_zero=False)
    _validate_numeric("tenor_months", tenor_months, allow_zero=False)
    _validate_numeric("annual_interest_rate", annual_interest_rate, allow_zero=True)

    input_warnings: list[str] = []
    collateral = _build_collateral(luas_tanah, luas_bangunan, kode_pos, kelurahan,
                                   appraisal_month, input_warnings)
    loan = _build_loan(loan_amount, tenor_months, annual_interest_rate, input_warnings)
```

Then replace the `run_job(...)` call inside `asyncio.create_task(...)` with:

```python
    task = asyncio.create_task(
        run_job(store, job.id, payload, bonus_accept_pct=pct, password=password,
                collateral=collateral, loan=loan, input_warnings=input_warnings)
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_api.py -v`
Expected: PASS (existing tests + 3 new tests)

- [ ] **Step 8: Commit**

```bash
git add ocr_orchestrator/api.py ocr_orchestrator/tests/test_api.py
git commit -m "feat(orchestrator): accept collateral + loan form fields, validate + wire"
```

---

## Task 8: Demo surface + docs + full-suite verification

**Files:**
- Modify: `ocr_orchestrator/api.py` (the `_UPLOAD_PAGE` HTML string)
- Modify: `.env.example` (repo root)
- Modify: `ocr_orchestrator/README.md`

- [ ] **Step 1: Add collateral + loan inputs to the upload page**

In `ocr_orchestrator/api.py`, in `_UPLOAD_PAGE`, find the `<div class="row">` that contains `Bonus accept %`. Insert these two rows immediately **before** it:

```html
 <div class="row">
   <label>Luas tanah m²: <input type="number" id="lt" step="any" placeholder="optional" style="width:90px"></label>
   <label>Luas bangunan m²: <input type="number" id="lb" step="any" placeholder="optional" style="width:90px"></label>
   <label>Kode pos: <input type="text" id="kp" placeholder="optional" style="width:90px"></label>
   <label>Kelurahan: <input type="text" id="kl" placeholder="optional" style="width:120px"></label>
 </div>
 <div class="row">
   <label>Loan amount: <input type="number" id="la" step="any" placeholder="optional" style="width:120px"></label>
   <label>Tenor (months): <input type="number" id="tn" step="1" placeholder="optional" style="width:90px"></label>
   <label>Annual rate: <input type="number" id="ar" step="any" placeholder="e.g. 0.105" style="width:90px"></label>
 </div>
```

In the same string's `<script>`, find the line `const pw=document.getElementById('pw').value;if(pw)fd.append('password',pw);` and insert immediately **after** it:

```javascript
 const addNum=(id,key)=>{const v=document.getElementById(id).value;if(v!=='')fd.append(key,v);};
 const addStr=(id,key)=>{const v=document.getElementById(id).value;if(v.trim()!=='')fd.append(key,v.trim());};
 addNum('lt','luas_tanah');addNum('lb','luas_bangunan');addStr('kp','kode_pos');addStr('kl','kelurahan');
 addNum('la','loan_amount');addNum('tn','tenor_months');addNum('ar','annual_interest_rate');
```

- [ ] **Step 2: Manually verify the page loads**

Run: `.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_api.py::TestApi::test_root_redirects_to_upload" -v`
Expected: PASS (the page string still parses and serves; the route is unchanged)

- [ ] **Step 3: Document the new env keys**

Read `.env.example` (repo root), then append this block at the end:

```ini
# --- ocr_orchestrator: FMV + decision ---
FMV_URL=http://127.0.0.1:8000
FMV_TIMEOUT_S=30
MAX_LTV=0.80
MAX_DSR=0.50
DEFAULT_EXISTING_INSTALLMENT=0.0   # placeholder until the SLIK service is wired
```

- [ ] **Step 4: Document the feature in the orchestrator README**

Read `ocr_orchestrator/README.md`, then add a short subsection describing: the optional `collateral` (`luas_tanah`, `luas_bangunan`, `kode_pos`, `kelurahan`, `appraisal_month`) and `loan` (`loan_amount`, `tenor_months`, `annual_interest_rate`) form fields on `POST /api/v1/applications`; that they drive the `fmv` and `decide` stages (which are `skipped` when absent); the `decision` result shape (`recommendation` + `ltv`/`dsr` checks); and that `house_fair_market_value` must be running at `FMV_URL` (default `:8000`) for the `fmv` stage. Note the SLIK existing-installment is a `0.0` placeholder.

- [ ] **Step 5: Run the FULL orchestrator suite**

Run: `.venv/Scripts/python -m pytest ocr_orchestrator/tests -v`
Expected: PASS (every test across config, models, jobs, decision, upstream, pipeline, api, identity, routing, verify)

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/api.py .env.example ocr_orchestrator/README.md
git commit -m "docs(orchestrator): expose FMV+decision on the upload page, env, README"
```

---

## Notes / deferred (not tasks)

- **Docker compose:** adding `house_fair_market_value` as a compose service (its own build context/Dockerfile) and injecting `FMV_URL` is a compose follow-up, not required for the local raw-uvicorn run. `house_fair_market_value` is **not** in `docker-compose.yml` today (per CLAUDE.md).
- **SLIK:** `DEFAULT_EXISTING_INSTALLMENT` stays `0.0` until the SLIK service exists; wiring it later is a single-value change plus reading the figure from that service in the pipeline.
- **FMV accuracy:** the `linear` backend is weak (land R² < 0). For a realistic demo decision, switch `house_fair_market_value/model_config.json` to `catboost` — operational config, no orchestrator change.

---

## Self-review (completed)

- **Spec coverage:** §4 stages → Tasks 3+6; §5 API inputs/validation → Task 7; §6 models → Task 2; §7 decision rule (annuity, LTV, DSR, recommendation matrix, FMV-warning passthrough) → Task 4; §8 error handling (skip/degrade/400/refer) → Tasks 6+7; §9 config → Task 1; §10 testing (decision unit, FMV client mocked, pipeline mocked, api 400) → Tasks 4/5/6/7; §11 out-of-scope respected (no SLIK/joint/persistence work). Covered.
- **Type consistency:** `compute_installment`/`decide` signatures, `DecisionResult`/`CheckResult`/`FmvResult`/`CollateralInput`/`LoanRequest` field names, and the `run_job(..., collateral=, loan=, input_warnings=)` keywords match across Tasks 2/4/6/7. `CheckResult.value` is `Optional[float]` to keep the zero-`fair_value` case JSON-serialisable (no `inf`).
- **Placeholders:** none — every step shows the concrete code or exact command.
