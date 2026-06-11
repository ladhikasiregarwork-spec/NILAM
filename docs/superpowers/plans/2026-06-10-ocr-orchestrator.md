# OCR Orchestrator Implementation Plan

> **Status — 2026-06-11: ✅ Implemented & shipped to `main` (tests passing).** The step checkboxes below are the original execution checklist, kept for history and not individually re-ticked (a few `(Optional)` manual/networked steps were not run).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sixth sibling service, `ocr_orchestrator` (port 8500), that accepts an unlabeled PDF bundle, classifies each document, routes it to the right OCR service, verifies salary slips against bank Gaji credits, and returns one monthly qualifying-income figure — via an async job + polling API.

**Architecture:** A flat Python package at the repo root following the existing monorepo conventions (shared `.env`/`.venv`/`requirements.txt`, `run_api.sh`, `Dockerfile`, compose entry). It HTTP-calls `ocr_classifier`, `ocr_slip`, `ocr_mutasi`, `ocr_sk` once each (async `httpx`) and **imports** `ocr_match`'s pure `match_all` matcher (no re-parsing). A `POST` creates an in-memory job and schedules a background `asyncio` task that runs five stages (classify → extract → verify → aggregate → assemble); a `GET` polls job status/result.

**Tech Stack:** Python 3.12, FastAPI, `httpx` (async), Pydantic v2 / `pydantic-settings`, stdlib `unittest` (incl. `IsolatedAsyncioTestCase`) + `fastapi.testclient` for tests.

**Spec:** `docs/superpowers/specs/2026-06-10-ocr-orchestrator-design.md`

**Branch:** `feat/ocr-orchestrator` (already checked out).

---

## Conventions for this plan

- All commands run **from the repo root** (the directory containing `requirements.txt`). The packages are flat and importable only from there.
- Use the project's Python interpreter. On this Windows machine that's `.venv\Scripts\python` (activate the venv, or prefix commands). The plan writes commands as `python …` assuming the venv is active.
- Tests live under `ocr_orchestrator/tests/` and run with `python -m unittest`.
- Commit after every task. Keep commits on `feat/ocr-orchestrator`.

## File structure (what each file owns)

```
ocr_orchestrator/
├── __init__.py          # __version__
├── config.py            # pydantic-settings: upstream URLs + limits (NO Azure keys)
├── models.py            # all Pydantic request/response/job types
├── jobs.py              # in-memory async job store (create/get/mutate, retention cap)
├── upstream.py          # async httpx clients: classify / slips / mutasi / sk + error types
├── routing.py           # pure: classifier results -> typed buckets + DocumentResult[]
├── verify.py            # build ParsedSlip/GajiCredit, set .month, call imported match_all
├── identity.py          # pure: resolve applicant name from slip -> mutasi -> sk
├── income.py            # pure: compute the IncomeBreakdown (the one business rule)
├── pipeline.py          # async run_job(): the 5-stage orchestration
├── api.py               # FastAPI app: POST/GET endpoints, /health, /upload, OpenAPI patch
├── run_api.sh           # repo-root launcher (mirrors ocr_match)
├── Dockerfile           # mirrors ocr_match; CMD uvicorn ocr_orchestrator.api:app :8500
├── README.md            # usage
└── tests/
    ├── __init__.py
    ├── test_income.py
    ├── test_jobs.py
    ├── test_routing.py
    ├── test_verify.py
    ├── test_identity.py
    ├── test_pipeline.py
    └── test_api.py
```

Plus repo-root edits: `.env.example` (new vars), `docker-compose.yml` (new service).

---

## Task 1: Package scaffold + config

**Files:**
- Create: `ocr_orchestrator/__init__.py`
- Create: `ocr_orchestrator/config.py`
- Create: `ocr_orchestrator/tests/__init__.py`
- Test: `ocr_orchestrator/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`ocr_orchestrator/tests/test_config.py`:
```python
import unittest

from ocr_orchestrator.config import Settings


class TestSettings(unittest.TestCase):
    def test_defaults(self):
        # Build directly (bypass .env) to assert the shipped defaults.
        s = Settings(_env_file=None)
        self.assertEqual(s.app_port, 8500)
        self.assertEqual(s.ocr_classifier_url, "http://127.0.0.1:8000")
        self.assertEqual(s.ocr_slip_url, "http://127.0.0.1:8200")
        self.assertEqual(s.ocr_mutasi_url, "http://127.0.0.1:8300")
        self.assertEqual(s.ocr_sk_url, "http://127.0.0.1:8100")
        self.assertEqual(s.default_bonus_accept_pct, 0.0)
        self.assertEqual(s.job_retention, 200)
        self.assertEqual(s.max_files, 50)

    def test_bonus_pct_is_float(self):
        s = Settings(_env_file=None)
        self.assertIsInstance(s.default_bonus_accept_pct, float)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest ocr_orchestrator.tests.test_config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator'`.

- [ ] **Step 3: Write the scaffolding**

`ocr_orchestrator/__init__.py`:
```python
"""NILAM OCR orchestrator service."""
__version__ = "0.1.0"
```

`ocr_orchestrator/tests/__init__.py`:
```python
```
(empty file)

`ocr_orchestrator/config.py`:
```python
"""Runtime configuration loaded once from .env at startup.

The orchestrator never calls Azure directly — it only fans out to the four
OCR services over HTTP — so it deliberately does NOT declare the
``AZURE_OPENAI_*`` settings the other services require. (Note: importing
``ocr_match.matcher`` does pull in ``ocr_match.config``, which *does* require
those keys at call time; the shared repo-root .env provides them in real runs.)
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of environment variables."""

    # Upstream OCR services (compose overrides these with service-DNS URLs).
    ocr_classifier_url: str = "http://127.0.0.1:8000"
    ocr_sk_url: str = "http://127.0.0.1:8100"
    ocr_slip_url: str = "http://127.0.0.1:8200"
    ocr_mutasi_url: str = "http://127.0.0.1:8300"

    # Service bind.
    app_host: str = "0.0.0.0"
    app_port: int = 8500

    # Timeouts & limits. The mutasi batch LLM parse can take ~30s; keep this
    # generous so a big bundle doesn't trip the upstream timeout.
    upstream_timeout_s: float = 180.0
    max_files: int = 50

    # Income: default analyst bonus-acceptance fraction (0.0 = bonus excluded
    # until an analyst opts in). Clamped to [0, 1] at the API boundary.
    default_bonus_accept_pct: float = 0.0

    # In-memory job store: keep at most this many most-recent jobs.
    job_retention: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — read .env once per process."""
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest ocr_orchestrator.tests.test_config -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/__init__.py ocr_orchestrator/config.py ocr_orchestrator/tests/__init__.py ocr_orchestrator/tests/test_config.py
git commit -m "feat(orchestrator): scaffold package + config"
```

---

## Task 2: Pydantic models

**Files:**
- Create: `ocr_orchestrator/models.py`
- Test: `ocr_orchestrator/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`ocr_orchestrator/tests/test_models.py`:
```python
import unittest

from ocr_orchestrator.models import (
    ApplicantInfo,
    ApplicationResult,
    DocumentResult,
    IncomeBreakdown,
    JobStage,
    JobStatusResponse,
    OrchestratorAudit,
    VerificationInfo,
)


class TestModels(unittest.TestCase):
    def test_document_result_defaults(self):
        d = DocumentResult(filename="a.pdf", document_type="mutasi",
                           confidence="high", status="extracted")
        self.assertIsNone(d.extracted)

    def test_applicant_reserved_fields_default_null(self):
        a = ApplicantInfo(name="BUDI SANTOSO", name_source="slip")
        self.assertIsNone(a.birth_date)
        self.assertIsNone(a.age)
        self.assertIsNone(a.nik)

    def test_job_stage_default_pending(self):
        s = JobStage(name="classify")
        self.assertEqual(s.status, "pending")
        self.assertIsNone(s.error)

    def test_application_result_assembles(self):
        result = ApplicationResult(
            documents=[],
            applicant=ApplicantInfo(),
            income=IncomeBreakdown(
                n_statement_months=0, avg_monthly_gaji_insentif=0.0,
                monthly_thr=0.0, bonus_total=0.0, bonus_accept_pct=0.0,
                bonus_monthly=0.0, monthly_qualifying_income=None,
                basis="none", verified_month_count=0, warnings=[],
            ),
            verification=VerificationInfo(),
            audit=OrchestratorAudit(),
        )
        self.assertEqual(result.income.basis, "none")

    def test_job_status_response_optional_result(self):
        r = JobStatusResponse(job_id="x", status="pending",
                              stages=[JobStage(name="classify")])
        self.assertIsNone(r.result)
        self.assertIsNone(r.error)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest ocr_orchestrator.tests.test_models -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.models'`.

- [ ] **Step 3: Write the models**

`ocr_orchestrator/models.py`:
```python
"""Pydantic request/response/job types for the orchestrator.

These double as FastAPI response schemas. ``extracted`` and ``matched_pairs``
hold loosely-typed upstream payloads, so they are plain dicts.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

JobState = Literal["pending", "running", "completed", "failed"]
StageState = Literal["pending", "running", "completed", "failed"]
DocStatus = Literal["extracted", "recognized_not_extracted", "unclassified"]
IncomeBasis = Literal["bank_verified", "bank_unverified", "slip_fallback", "none"]


class DocumentResult(BaseModel):
    """One uploaded file: its classification and (when applicable) extraction."""
    filename: str
    document_type: str
    confidence: Optional[str] = None
    status: DocStatus
    extracted: Optional[dict[str, Any]] = None


class ApplicantInfo(BaseModel):
    """Applicant identity. v1 fills ``name`` only; the rest await the KTP service."""
    name: Optional[str] = None
    name_source: Optional[str] = None  # "slip" | "mutasi" | "sk" | None
    birth_date: Optional[str] = None   # reserved — KTP service (follow-on)
    age: Optional[int] = None          # reserved — derived from birth_date
    nik: Optional[str] = None          # reserved — KTP service (follow-on)


class IncomeBreakdown(BaseModel):
    """The §7 monthly qualifying-income breakdown."""
    n_statement_months: int
    avg_monthly_gaji_insentif: float
    monthly_thr: float
    bonus_total: float
    bonus_accept_pct: float
    bonus_monthly: float
    monthly_qualifying_income: Optional[float]
    basis: IncomeBasis
    verified_month_count: int
    warnings: list[str] = Field(default_factory=list)


class VerificationInfo(BaseModel):
    """Summary of the slip<->Gaji verification."""
    matched_count: int = 0
    verified_month_count: int = 0
    matched_pairs: list[dict[str, Any]] = Field(default_factory=list)


class OrchestratorAudit(BaseModel):
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
    classifier_errors: list[str] = Field(default_factory=list)
    extractor_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplicationResult(BaseModel):
    documents: list[DocumentResult]
    applicant: ApplicantInfo
    income: Optional[IncomeBreakdown]
    verification: VerificationInfo
    audit: OrchestratorAudit


class JobStage(BaseModel):
    name: str
    status: StageState = "pending"
    error: Optional[str] = None


class AcceptedResponse(BaseModel):
    """Body of the 202 returned by POST /api/v1/applications."""
    job_id: str
    status: JobState
    status_url: str


class JobStatusResponse(BaseModel):
    """Body of GET /api/v1/applications/{job_id}."""
    job_id: str
    status: JobState
    stages: list[JobStage]
    result: Optional[ApplicationResult] = None
    error: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest ocr_orchestrator.tests.test_models -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/tests/test_models.py
git commit -m "feat(orchestrator): pydantic models"
```

---

## Task 3: Income computation (the one business rule)

**Files:**
- Create: `ocr_orchestrator/income.py`
- Test: `ocr_orchestrator/tests/test_income.py`

This is the core logic — test it thoroughly first.

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_income.py`:
```python
import unittest

from ocr_orchestrator.income import compute_income


def _credit(category, amount, tanggal):
    return {"category": category, "amount": amount, "tanggal": tanggal}


class TestComputeIncome(unittest.TestCase):
    def test_bank_verified_full_formula(self):
        # 2 months of Gaji 10,000,000 + Insentif 500,000; one THR 12,000,000;
        # one Bonus 24,000,000; analyst accepts 50% of bonus.
        credits = [
            _credit("Gaji", 10_000_000, "2025-01-25"),
            _credit("Insentif", 500_000, "2025-01-25"),
            _credit("Gaji", 10_000_000, "2025-02-25"),
            _credit("Insentif", 500_000, "2025-02-25"),
            _credit("THR", 12_000_000, "2025-02-25"),
            _credit("Bonus", 24_000_000, "2025-02-25"),
        ]
        out = compute_income(
            credits=credits,
            verified_months={"2025-01", "2025-02"},
            slip_total_paids=[10_500_000.0],
            bonus_accept_pct=0.5,
        )
        self.assertEqual(out.basis, "bank_verified")
        self.assertEqual(out.n_statement_months, 2)
        self.assertEqual(out.avg_monthly_gaji_insentif, 10_500_000)   # (21,000,000)/2
        self.assertEqual(out.monthly_thr, 1_000_000)                  # 12,000,000/12
        self.assertEqual(out.bonus_total, 24_000_000)
        self.assertEqual(out.bonus_monthly, 1_000_000)                # 24,000,000*0.5/12
        self.assertEqual(out.monthly_qualifying_income, 12_500_000)
        self.assertEqual(out.verified_month_count, 2)

    def test_bonus_excluded_at_zero_pct(self):
        credits = [_credit("Gaji", 9_000_000, "2025-03-25"),
                   _credit("Bonus", 60_000_000, "2025-03-25")]
        out = compute_income(credits=credits, verified_months={"2025-03"},
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.bonus_total, 60_000_000)
        self.assertEqual(out.bonus_monthly, 0.0)
        self.assertEqual(out.monthly_qualifying_income, 9_000_000)

    def test_bank_unverified_when_no_match(self):
        credits = [_credit("Gaji", 8_000_000, "2025-04-25")]
        out = compute_income(credits=credits, verified_months=set(),
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "bank_unverified")
        self.assertEqual(out.verified_month_count, 0)
        self.assertEqual(out.monthly_qualifying_income, 8_000_000)

    def test_n_months_counts_distinct_credit_months_not_calendar_span(self):
        # Gaji in Jan and Mar only (Feb skipped). Denominator must be 2, not 3.
        credits = [_credit("Gaji", 10_000_000, "2025-01-25"),
                   _credit("Gaji", 10_000_000, "2025-03-25")]
        out = compute_income(credits=credits, verified_months={"2025-01"},
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.n_statement_months, 2)
        self.assertEqual(out.avg_monthly_gaji_insentif, 10_000_000)

    def test_slip_fallback_when_no_mutasi(self):
        out = compute_income(credits=[], verified_months=set(),
                             slip_total_paids=[7_000_000.0, 9_000_000.0],
                             bonus_accept_pct=0.5)
        self.assertEqual(out.basis, "slip_fallback")
        self.assertEqual(out.avg_monthly_gaji_insentif, 8_000_000)   # mean of the two slips
        self.assertEqual(out.monthly_thr, 0.0)
        self.assertEqual(out.bonus_monthly, 0.0)
        self.assertEqual(out.monthly_qualifying_income, 8_000_000)
        self.assertTrue(out.warnings)

    def test_none_when_nothing(self):
        out = compute_income(credits=[], verified_months=set(),
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "none")
        self.assertIsNone(out.monthly_qualifying_income)
        self.assertTrue(out.warnings)

    def test_mutasi_present_but_no_salary_credits_falls_back_to_slip(self):
        # Only Lainnya credits -> no Gaji/Insentif months -> use slip.
        credits = [_credit("Lainnya", 50_000, "2025-05-02")]
        out = compute_income(credits=credits, verified_months=set(),
                             slip_total_paids=[6_000_000.0], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "slip_fallback")
        self.assertEqual(out.monthly_qualifying_income, 6_000_000)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_income -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.income'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/income.py`:
```python
"""Pure monthly-qualifying-income aggregation (spec §7).

The single business rule in the orchestrator. Bank statement (mutasi) is the
source of truth; slip total_paid is an unverified fallback.

    monthly_qualifying_income
      = avg_monthly(Gaji + Insentif)       over distinct salary months
      + total(THR) / 12
      + total(Bonus) * bonus_accept_pct / 12
"""
from __future__ import annotations

from typing import Any, Iterable

from .models import IncomeBreakdown

_SALARY = ("Gaji", "Insentif")


def _month(tanggal: Any) -> str | None:
    if isinstance(tanggal, str) and len(tanggal) >= 7:
        return tanggal[:7]
    return None


def compute_income(
    *,
    credits: list[dict[str, Any]],
    verified_months: Iterable[str],
    slip_total_paids: list[float],
    bonus_accept_pct: float,
) -> IncomeBreakdown:
    """Compute the income breakdown.

    Args:
        credits: every mutasi credit dict (all categories), each with
            ``category``, ``amount``, ``tanggal`` (ISO ``YYYY-MM-DD``).
        verified_months: YYYY-MM buckets confirmed by an ocr_match slip<->Gaji
            pair. Non-empty -> ``bank_verified``.
        slip_total_paids: ``total_paid`` from each parsed slip (fallback only).
        bonus_accept_pct: analyst bonus-acceptance fraction in [0, 1].
    """
    verified = {m for m in verified_months if m}

    salary = [c for c in credits if c.get("category") in _SALARY]
    salary_months = {_month(c.get("tanggal")) for c in salary}
    salary_months.discard(None)
    n_months = len(salary_months)

    total_thr = sum(float(c["amount"]) for c in credits if c.get("category") == "THR")
    total_bonus = sum(float(c["amount"]) for c in credits if c.get("category") == "Bonus")
    monthly_thr = total_thr / 12.0
    bonus_monthly = total_bonus * bonus_accept_pct / 12.0

    warnings: list[str] = []

    if n_months >= 1:
        avg = sum(float(c["amount"]) for c in salary) / n_months
        income = avg + monthly_thr + bonus_monthly
        basis = "bank_verified" if verified else "bank_unverified"
        return IncomeBreakdown(
            n_statement_months=n_months,
            avg_monthly_gaji_insentif=avg,
            monthly_thr=monthly_thr,
            bonus_total=total_bonus,
            bonus_accept_pct=bonus_accept_pct,
            bonus_monthly=bonus_monthly,
            monthly_qualifying_income=income,
            basis=basis,
            verified_month_count=len(verified),
            warnings=warnings,
        )

    if slip_total_paids:
        avg = sum(slip_total_paids) / len(slip_total_paids)
        warnings.append(
            "No bank salary credits found; using slip total_paid (unverified)."
        )
        return IncomeBreakdown(
            n_statement_months=0,
            avg_monthly_gaji_insentif=avg,
            monthly_thr=0.0,
            bonus_total=0.0,
            bonus_accept_pct=bonus_accept_pct,
            bonus_monthly=0.0,
            monthly_qualifying_income=avg,
            basis="slip_fallback",
            verified_month_count=0,
            warnings=warnings,
        )

    warnings.append(
        "No bank statement and no salary slip; income could not be computed."
    )
    return IncomeBreakdown(
        n_statement_months=0,
        avg_monthly_gaji_insentif=0.0,
        monthly_thr=0.0,
        bonus_total=0.0,
        bonus_accept_pct=bonus_accept_pct,
        bonus_monthly=0.0,
        monthly_qualifying_income=None,
        basis="none",
        verified_month_count=0,
        warnings=warnings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_income -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/income.py ocr_orchestrator/tests/test_income.py
git commit -m "feat(orchestrator): income aggregation with trust hierarchy"
```

---

## Task 4: In-memory job store

**Files:**
- Create: `ocr_orchestrator/jobs.py`
- Test: `ocr_orchestrator/tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_jobs.py`:
```python
import unittest

from ocr_orchestrator.jobs import JobStore


class TestJobStore(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_get(self):
        store = JobStore(retention=10)
        job = await store.create()
        self.assertEqual(job.status, "pending")
        self.assertEqual([s.name for s in job.stages],
                         ["classify", "extract", "verify", "aggregate"])
        fetched = await store.get(job.id)
        self.assertIs(fetched, job)

    async def test_get_unknown_returns_none(self):
        store = JobStore(retention=10)
        self.assertIsNone(await store.get("nope"))

    async def test_set_stage_and_status(self):
        store = JobStore(retention=10)
        job = await store.create()
        await store.set_status(job.id, "running")
        await store.set_stage(job.id, "classify", "completed")
        self.assertEqual(job.status, "running")
        stage = next(s for s in job.stages if s.name == "classify")
        self.assertEqual(stage.status, "completed")

    async def test_fail_sets_error_and_status(self):
        store = JobStore(retention=10)
        job = await store.create()
        await store.fail(job.id, "boom")
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, "boom")

    async def test_retention_evicts_oldest(self):
        store = JobStore(retention=2)
        a = await store.create()
        b = await store.create()
        c = await store.create()
        self.assertIsNone(await store.get(a.id))   # evicted
        self.assertIsNotNone(await store.get(b.id))
        self.assertIsNotNone(await store.get(c.id))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_jobs -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.jobs'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/jobs.py`:
```python
"""In-memory async job store.

v1 limitation (documented in the spec): single uvicorn worker only and jobs
are lost on restart — there is no persistence. An ``asyncio.Lock`` serialises
mutations; ``OrderedDict`` + ``retention`` bounds memory growth.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from .models import ApplicationResult, JobStage, JobState, StageState

_DEFAULT_STAGES = ("classify", "extract", "verify", "aggregate")


@dataclass
class Job:
    id: str
    status: JobState = "pending"
    stages: list[JobStage] = field(default_factory=list)
    result: Optional[ApplicationResult] = None
    error: Optional[str] = None
    # Kept so the background task isn't garbage-collected mid-run. Never serialised.
    task: Optional[asyncio.Task] = None


class JobStore:
    def __init__(self, retention: int = 200) -> None:
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = asyncio.Lock()
        self._retention = max(1, retention)

    async def create(self) -> Job:
        async with self._lock:
            job = Job(
                id=uuid.uuid4().hex,
                stages=[JobStage(name=n) for n in _DEFAULT_STAGES],
            )
            self._jobs[job.id] = job
            while len(self._jobs) > self._retention:
                self._jobs.popitem(last=False)  # evict oldest
            return job

    async def get(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def set_status(self, job_id: str, status: JobState) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status

    async def set_stage(
        self, job_id: str, name: str, status: StageState,
        error: Optional[str] = None,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for stage in job.stages:
                if stage.name == name:
                    stage.status = status
                    stage.error = error
                    break

    async def set_result(self, job_id: str, result: ApplicationResult) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.result = result
                job.status = "completed"

    async def fail(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.error = error
                job.status = "failed"

    async def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.task = task
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_jobs -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/jobs.py ocr_orchestrator/tests/test_jobs.py
git commit -m "feat(orchestrator): in-memory async job store"
```

---

## Task 5: Upstream HTTP clients

**Files:**
- Create: `ocr_orchestrator/upstream.py`

These are thin async adapters mirroring `ocr_match/upstream.py`. They are exercised indirectly by the pipeline test (Task 9, with these functions mocked) and the manual smoke (Task 12), so this task has no isolated unit test — matching `ocr_match`, which also unit-tests through its pipeline rather than its HTTP plumbing. Verification here is an import + signature check.

- [ ] **Step 1: Write the implementation**

`ocr_orchestrator/upstream.py`:
```python
"""Async httpx clients for the four OCR services.

Each function takes already-read ``(filename, bytes)`` tuples and returns the
loosely-typed JSON the orchestrator pipeline consumes. We never re-parse PDFs
here; the services own all PDF/OCR I/O.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class UpstreamUnreachableError(RuntimeError):
    """The upstream service refused the connection (network/DNS error)."""


class UpstreamHttpError(RuntimeError):
    """The upstream service answered with a 4xx/5xx response."""

    def __init__(self, service: str, status_code: int, body: str) -> None:
        super().__init__(f"{service} returned {status_code}: {body[:300]}")
        self.service = service
        self.status_code = status_code
        self.body = body


def _files(pdfs: list[tuple[str, bytes]]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/pdf")) for name, data in pdfs]


async def _post(service: str, url: str, *, files, data=None, params=None) -> dict[str, Any]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_s) as client:
            r = await client.post(url, files=files, data=data or {}, params=params or {})
    except httpx.ConnectError as exc:
        raise UpstreamUnreachableError(f"{service} not reachable at {url}: {exc}") from exc
    if r.status_code >= 400:
        raise UpstreamHttpError(service, r.status_code, r.text)
    return r.json()


async def classify_documents(pdfs: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
    """POST every file to ocr_classifier:/classify-batch. Returns ``results[]``
    (one dict per file: ``filename``, ``document_type``, ``confidence``, ...)."""
    s = get_settings()
    payload = await _post(
        "ocr_classifier", f"{s.ocr_classifier_url}/classify-batch", files=_files(pdfs)
    )
    return payload.get("results", [])


async def parse_slips(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> list[dict[str, Any]]:
    """POST slips to ocr_slip:/parse. Returns ``documents[]`` (English-keyed
    per-slip dicts: ``worker_name``, ``total_paid``, ``period``, ...)."""
    s = get_settings()
    data = {"password": password} if password else {}
    payload = await _post(
        "ocr_slip", f"{s.ocr_slip_url}/parse",
        files=_files(pdfs), data=data, params={"ocr": "auto"},
    )
    return payload.get("documents", [])


async def extract_mutations(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> dict[str, Any]:
    """POST bank statements to ocr_mutasi:/extract-batch. Returns the FULL batch
    payload (``files[]``, ``credits[]`` across all categories, ``audit``).

    Unlike ocr_match (Gaji-only), the orchestrator needs every category for the
    income formula, plus ``files[].account.nama`` for applicant-name fallback."""
    s = get_settings()
    data = {"password": password} if password else {}
    return await _post(
        "ocr_mutasi", f"{s.ocr_mutasi_url}/api/v1/mutations/extract-batch",
        files=_files(pdfs), data=data, params={"classify": "true"},
    )


async def parse_sk(
    pdfs: list[tuple[str, bytes]], password: str | None = None
) -> dict[str, Any]:
    """POST employment letters to ocr_sk:/parse. Returns the raw response
    (``summary``, ``extracted``, ...)."""
    s = get_settings()
    data = {"password": password} if password else {}
    return await _post(
        "ocr_sk", f"{s.ocr_sk_url}/parse", files=_files(pdfs), data=data
    )
```

- [ ] **Step 2: Verify it imports cleanly**

Run:
```bash
python -c "from ocr_orchestrator import upstream; print(sorted(n for n in dir(upstream) if not n.startswith('_')))"
```
Expected output includes: `['UpstreamHttpError', 'UpstreamUnreachableError', 'classify_documents', 'extract_mutations', 'parse_sk', 'parse_slips', ...]`

- [ ] **Step 3: Commit**

```bash
git add ocr_orchestrator/upstream.py
git commit -m "feat(orchestrator): async upstream HTTP clients"
```

---

## Task 6: Document routing / bucketing

**Files:**
- Create: `ocr_orchestrator/routing.py`
- Test: `ocr_orchestrator/tests/test_routing.py`

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_routing.py`:
```python
import unittest

from ocr_orchestrator.routing import route_documents


def _cls(filename, doc_type, conf="high"):
    return {"filename": filename, "document_type": doc_type, "confidence": conf}


class TestRouteDocuments(unittest.TestCase):
    def setUp(self):
        self.files = [
            ("slip1.pdf", b"a"), ("mut1.pdf", b"b"), ("sk1.pdf", b"c"),
            ("ktp1.pdf", b"d"), ("kk1.pdf", b"e"), ("weird.pdf", b"f"),
        ]
        self.classifications = [
            _cls("slip1.pdf", "slip"), _cls("mut1.pdf", "mutasi"),
            _cls("sk1.pdf", "sk"), _cls("ktp1.pdf", "ktp"),
            _cls("kk1.pdf", "kk"), _cls("weird.pdf", "unknown"),
        ]

    def test_buckets_by_type(self):
        buckets, docs, warnings = route_documents(self.classifications, self.files)
        self.assertEqual([n for n, _ in buckets.slips], ["slip1.pdf"])
        self.assertEqual([n for n, _ in buckets.mutasi], ["mut1.pdf"])
        self.assertEqual([n for n, _ in buckets.sk], ["sk1.pdf"])

    def test_document_status_mapping(self):
        _, docs, _ = route_documents(self.classifications, self.files)
        status = {d.filename: d.status for d in docs}
        self.assertEqual(status["slip1.pdf"], "extracted")
        self.assertEqual(status["ktp1.pdf"], "recognized_not_extracted")
        self.assertEqual(status["kk1.pdf"], "recognized_not_extracted")
        self.assertEqual(status["weird.pdf"], "unclassified")

    def test_unknown_emits_warning(self):
        _, _, warnings = route_documents(self.classifications, self.files)
        self.assertTrue(any("weird.pdf" in w for w in warnings))

    def test_one_doc_per_uploaded_file(self):
        _, docs, _ = route_documents(self.classifications, self.files)
        self.assertEqual(len(docs), len(self.files))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_routing -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.routing'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/routing.py`:
```python
"""Pure routing: classifier results -> typed file buckets + DocumentResult[].

Bucketing is by ``document_type``. ktp/kk are recognized but not extracted in
v1; unknown is flagged with a warning. Both still appear in ``documents[]``."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import DocumentResult

Pdf = tuple[str, bytes]


@dataclass
class Buckets:
    slips: list[Pdf] = field(default_factory=list)
    mutasi: list[Pdf] = field(default_factory=list)
    sk: list[Pdf] = field(default_factory=list)
    ktp: list[Pdf] = field(default_factory=list)
    kk: list[Pdf] = field(default_factory=list)
    unknown: list[Pdf] = field(default_factory=list)


def route_documents(
    classifications: list[dict[str, Any]],
    files: list[Pdf],
) -> tuple[Buckets, list[DocumentResult], list[str]]:
    """Group uploaded files by classified type.

    Args:
        classifications: ocr_classifier results (``filename``, ``document_type``,
            ``confidence``).
        files: the original ``(filename, bytes)`` uploads.

    Returns:
        (buckets, document_results, warnings). One DocumentResult per file.
    """
    by_name: dict[str, bytes] = {name: data for name, data in files}
    buckets = Buckets()
    docs: list[DocumentResult] = []
    warnings: list[str] = []

    _extracted = {"slip", "mutasi", "sk"}
    _recognized = {"ktp", "kk"}

    for c in classifications:
        filename = c.get("filename", "")
        doc_type = c.get("document_type", "unknown")
        data = by_name.get(filename, b"")
        pair: Pdf = (filename, data)

        if doc_type == "slip":
            buckets.slips.append(pair)
        elif doc_type == "mutasi":
            buckets.mutasi.append(pair)
        elif doc_type == "sk":
            buckets.sk.append(pair)
        elif doc_type == "ktp":
            buckets.ktp.append(pair)
        elif doc_type == "kk":
            buckets.kk.append(pair)
        else:
            buckets.unknown.append(pair)

        if doc_type in _extracted:
            status = "extracted"
        elif doc_type in _recognized:
            status = "recognized_not_extracted"
        else:
            status = "unclassified"
            warnings.append(f"{filename!r} classified as unknown — skipped.")

        docs.append(DocumentResult(
            filename=filename, document_type=doc_type,
            confidence=c.get("confidence"), status=status,
        ))

    return buckets, docs, warnings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_routing -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/routing.py ocr_orchestrator/tests/test_routing.py
git commit -m "feat(orchestrator): document routing/bucketing"
```

---

## Task 7: Slip↔Gaji verification (reuse imported matcher)

**Files:**
- Create: `ocr_orchestrator/verify.py`
- Test: `ocr_orchestrator/tests/test_verify.py`

**Gotcha:** `ocr_match.matcher.match_all` calls `ocr_match.config.get_settings()`, which requires `AZURE_OPENAI_*` env vars at call time. The test must patch that so it can run without secrets.

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_verify.py`:
```python
import unittest
from unittest import mock

from ocr_orchestrator import verify


class _FakeSettings:
    match_amount_tolerance_rp = 1.0


class TestVerify(unittest.TestCase):
    def setUp(self):
        # match_all reads tolerance from ocr_match.config via this name.
        patcher = mock.patch("ocr_match.matcher.get_settings",
                             return_value=_FakeSettings())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_exact_amount_next_month_match(self):
        slip_docs = [{"source_file": "Slip_Feb_2025.pdf",
                      "worker_name": "BUDI", "total_paid": 9_500_000.0,
                      "period": "2025-02"}]
        gaji = [{"source_file": "Mar.pdf", "tanggal": "2025-03-25",
                 "keterangan": "GAJI", "amount": 9_500_000.0, "page": 1,
                 "category": "Gaji"}]
        matches, verified_months = verify.verify_slips_credits(slip_docs, gaji)
        self.assertEqual(len(matches), 1)
        self.assertEqual(verified_months, {"2025-03"})

    def test_no_match_returns_empty_verified(self):
        slip_docs = [{"source_file": "s.pdf", "total_paid": 1_000_000.0,
                      "period": "2025-02"}]
        gaji = [{"source_file": "m.pdf", "tanggal": "2025-03-25",
                 "keterangan": "GAJI", "amount": 9_999_999.0, "page": 1,
                 "category": "Gaji"}]
        matches, verified_months = verify.verify_slips_credits(slip_docs, gaji)
        self.assertEqual(matches, [])
        self.assertEqual(verified_months, set())

    def test_empty_inputs(self):
        matches, verified_months = verify.verify_slips_credits([], [])
        self.assertEqual(matches, [])
        self.assertEqual(verified_months, set())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_verify -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.verify'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/verify.py`:
```python
"""Slip <-> Gaji verification by reusing ocr_match's deterministic matcher.

We import ``match_all`` (pure logic) and ocr_match's month-derivation helpers
rather than calling ocr_match over HTTP — that would re-parse the slip and
mutasi PDFs a second time (spec Approach B). We feed it the data the
orchestrator already fetched.
"""
from __future__ import annotations

from typing import Any

from ocr_match.matcher import match_all
from ocr_match.models import GajiCredit, ParsedSlip
from ocr_match.pipeline import _credit_month, _slip_month


def verify_slips_credits(
    slip_docs: list[dict[str, Any]],
    gaji_credit_dicts: list[dict[str, Any]],
) -> tuple[list[Any], set[str]]:
    """Pair slips against Gaji credits.

    Args:
        slip_docs: ocr_slip ``documents[]`` dicts.
        gaji_credit_dicts: mutasi credits already filtered to ``category=='Gaji'``.

    Returns:
        (matches, verified_months) where ``matches`` is a list of
        ``ocr_match.models.MatchPair`` and ``verified_months`` is the set of
        YYYY-MM buckets that produced a match.
    """
    slips = [ParsedSlip(**d) for d in slip_docs]
    credits = [GajiCredit(**c) for c in gaji_credit_dicts]
    for s in slips:
        s.month = _slip_month(s)
    for c in credits:
        c.month = _credit_month(c)

    matches, _unmatched_slips, _unmatched_credits = match_all(slips, credits)
    verified_months = {m.credit.month for m in matches if m.credit.month}
    return matches, verified_months
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_verify -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/verify.py ocr_orchestrator/tests/test_verify.py
git commit -m "feat(orchestrator): slip<->Gaji verification via imported matcher"
```

---

## Task 8: Applicant name resolution

**Files:**
- Create: `ocr_orchestrator/identity.py`
- Test: `ocr_orchestrator/tests/test_identity.py`

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_identity.py`:
```python
import unittest

from ocr_orchestrator.identity import resolve_applicant_name


class TestResolveApplicantName(unittest.TestCase):
    def test_prefers_slip(self):
        name, src = resolve_applicant_name(
            slip_docs=[{"worker_name": "BUDI SANTOSO"}],
            mutasi_accounts=[{"nama": "B SANTOSO"}],
            sk_responses=[{"summary": {"worker_name": "BUDI"}}],
        )
        self.assertEqual(name, "BUDI SANTOSO")
        self.assertEqual(src, "slip")

    def test_falls_back_to_mutasi(self):
        name, src = resolve_applicant_name(
            slip_docs=[{"worker_name": None}],
            mutasi_accounts=[{"nama": "SITI AMINAH"}],
            sk_responses=[],
        )
        self.assertEqual(name, "SITI AMINAH")
        self.assertEqual(src, "mutasi")

    def test_falls_back_to_sk_nested(self):
        name, src = resolve_applicant_name(
            slip_docs=[],
            mutasi_accounts=[],
            sk_responses=[{"summary": {"dokumen": [{"nama_pekerja": "AGUS"}]}}],
        )
        self.assertEqual(name, "AGUS")
        self.assertEqual(src, "sk")

    def test_none_when_nothing(self):
        name, src = resolve_applicant_name([], [], [])
        self.assertIsNone(name)
        self.assertIsNone(src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_identity -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.identity'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/identity.py`:
```python
"""Pure applicant-name resolution (spec §6/§7).

v1 derives only the name, in precedence order slip -> mutasi -> sk. The KTP
service (name / birth_date / nik) is a follow-on. The SK shape varies, so the
SK lookup recursively searches for a worker-name key at any depth.
"""
from __future__ import annotations

from typing import Any, Optional

_SK_NAME_KEYS = ("worker_name", "nama_pekerja")


def _search_key(node: Any, keys: tuple[str, ...]) -> Optional[str]:
    """First non-empty string value under any of ``keys``, searched recursively."""
    if isinstance(node, dict):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in node.values():
            found = _search_key(v, keys)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _search_key(item, keys)
            if found:
                return found
    return None


def resolve_applicant_name(
    slip_docs: list[dict[str, Any]],
    mutasi_accounts: list[dict[str, Any]],
    sk_responses: list[dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(name, source)`` where source is 'slip' | 'mutasi' | 'sk' | None."""
    for d in slip_docs:
        v = d.get("worker_name")
        if isinstance(v, str) and v.strip():
            return v.strip(), "slip"
    for acc in mutasi_accounts:
        v = acc.get("nama")
        if isinstance(v, str) and v.strip():
            return v.strip(), "mutasi"
    for sk in sk_responses:
        v = _search_key(sk, _SK_NAME_KEYS)
        if v:
            return v, "sk"
    return None, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_identity -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/identity.py ocr_orchestrator/tests/test_identity.py
git commit -m "feat(orchestrator): applicant name resolution"
```

---

## Task 9: Pipeline orchestration (`run_job`)

**Files:**
- Create: `ocr_orchestrator/pipeline.py`
- Test: `ocr_orchestrator/tests/test_pipeline.py`

The pipeline imports upstream via `from . import upstream` so tests can patch
`ocr_orchestrator.upstream.<fn>`. It also patches `ocr_match.matcher.get_settings`
(verify uses the real matcher).

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_pipeline.py`:
```python
import unittest
from unittest import mock

from ocr_orchestrator import pipeline
from ocr_orchestrator.jobs import JobStore


class _FakeMatchSettings:
    match_amount_tolerance_rp = 1.0


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


def _async_raise(exc):
    async def _fn(*args, **kwargs):
        raise exc
    return _fn


class TestRunJob(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p = mock.patch("ocr_match.matcher.get_settings",
                       return_value=_FakeMatchSettings())
        self.addCleanup(p.stop)
        p.start()

    async def test_happy_path_bank_verified(self):
        files = [("slip_feb.pdf", b"a"), ("mut_mar.pdf", b"b")]
        classify = _async([
            {"filename": "slip_feb.pdf", "document_type": "slip", "confidence": "high"},
            {"filename": "mut_mar.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        slips = _async([{"source_file": "slip_feb.pdf", "worker_name": "BUDI",
                         "total_paid": 9_500_000.0, "period": "2025-02"}])
        mutasi = _async({
            "files": [{"filename": "mut_mar.pdf",
                       "account": {"nama": "BUDI SANTOSO"}}],
            "credits": [{"source_file": "mut_mar.pdf", "tanggal": "2025-03-25",
                         "keterangan": "GAJI", "amount": 9_500_000.0, "page": 1,
                         "category": "Gaji"}],
            "audit": {},
        })
        sk = _async({"summary": {}})

        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)

        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.result)
        self.assertEqual(job.result.income.basis, "bank_verified")
        self.assertEqual(job.result.income.monthly_qualifying_income, 9_500_000)
        self.assertEqual(job.result.applicant.name, "BUDI")
        self.assertEqual(job.result.applicant.name_source, "slip")
        self.assertEqual(job.result.verification.verified_month_count, 1)

    async def test_classifier_down_fails_job(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files = [("x.pdf", b"a")]
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents",
                               _async_raise(UpstreamUnreachableError("classifier down"))):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("classifier", job.error)

    async def test_extractor_down_degrades_not_fails(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files = [("slip.pdf", b"a"), ("mut.pdf", b"b")]
        classify = _async([
            {"filename": "slip.pdf", "document_type": "slip", "confidence": "high"},
            {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        slips = _async([{"source_file": "slip.pdf", "worker_name": "SITI",
                         "total_paid": 6_000_000.0, "period": "2025-02"}])
        sk = _async({"summary": {}})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations",
                               _async_raise(UpstreamUnreachableError("mutasi down"))), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.income.basis, "slip_fallback")
        self.assertTrue(job.result.audit.extractor_errors)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_pipeline -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.pipeline'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/pipeline.py`:
```python
"""Async five-stage orchestration: classify -> extract -> verify -> aggregate
-> assemble. Updates the job's stages as it progresses.

Imported as ``from . import upstream`` so tests can patch the upstream calls.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from . import upstream
from .identity import resolve_applicant_name
from .income import compute_income
from .jobs import JobStore
from .models import (
    ApplicantInfo,
    ApplicationResult,
    OrchestratorAudit,
    VerificationInfo,
)
from .routing import route_documents
from .verify import verify_slips_credits

logger = logging.getLogger("ocr_orchestrator.pipeline")

_UpstreamError = (upstream.UpstreamUnreachableError, upstream.UpstreamHttpError)


def _match_pair_view(pair: Any) -> dict[str, Any]:
    return {
        "slip_file": pair.slip.source_file,
        "credit_tanggal": pair.credit.tanggal,
        "amount": pair.credit.amount,
        "month": pair.credit.month,
        "match_pattern": pair.match_pattern,
    }


async def run_job(
    store: JobStore,
    job_id: str,
    files: list[tuple[str, bytes]],
    *,
    bonus_accept_pct: float,
    password: str | None,
) -> None:
    """Run the whole pipeline for one job, mutating job state in ``store``."""
    timings: dict[str, float] = {}
    audit = OrchestratorAudit()
    await store.set_status(job_id, "running")

    # ---- Stage 1: classify -------------------------------------------------
    await store.set_stage(job_id, "classify", "running")
    t0 = time.perf_counter()
    try:
        classifications = await upstream.classify_documents(files)
    except _UpstreamError as exc:
        await store.set_stage(job_id, "classify", "failed", str(exc))
        await store.fail(job_id, f"classifier: {exc}")
        return
    timings["classify"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "classify", "completed")

    buckets, doc_results, route_warnings = route_documents(classifications, files)
    audit.warnings.extend(route_warnings)

    # ---- Stage 2: extract (concurrent) ------------------------------------
    await store.set_stage(job_id, "extract", "running")
    t0 = time.perf_counter()

    async def _slips() -> list[dict[str, Any]]:
        if not buckets.slips:
            return []
        return await upstream.parse_slips(buckets.slips, password=password)

    async def _mutasi() -> dict[str, Any]:
        if not buckets.mutasi:
            return {"files": [], "credits": [], "audit": {}}
        return await upstream.extract_mutations(buckets.mutasi, password=password)

    async def _sk() -> dict[str, Any]:
        if not buckets.sk:
            return {}
        return await upstream.parse_sk(buckets.sk, password=password)

    slip_res, mutasi_res, sk_res = await asyncio.gather(
        _slips(), _mutasi(), _sk(), return_exceptions=True
    )

    slip_docs: list[dict[str, Any]] = []
    mutasi_payload: dict[str, Any] = {"files": [], "credits": [], "audit": {}}
    sk_response: dict[str, Any] = {}

    if isinstance(slip_res, Exception):
        audit.extractor_errors.append(f"ocr_slip: {slip_res}")
    else:
        slip_docs = slip_res
    if isinstance(mutasi_res, Exception):
        audit.extractor_errors.append(f"ocr_mutasi: {mutasi_res}")
    else:
        mutasi_payload = mutasi_res
    if isinstance(sk_res, Exception):
        audit.extractor_errors.append(f"ocr_sk: {sk_res}")
    else:
        sk_response = sk_res

    timings["extract"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "extract", "completed")

    # Attach per-document extraction payloads (by filename).
    slip_by_file = {d.get("source_file"): d for d in slip_docs}
    mut_files = mutasi_payload.get("files", [])
    mut_by_file = {f.get("filename"): f for f in mut_files}
    for d in doc_results:
        if d.document_type == "slip":
            d.extracted = slip_by_file.get(d.filename)
        elif d.document_type == "mutasi":
            d.extracted = mut_by_file.get(d.filename)
        elif d.document_type == "sk":
            d.extracted = sk_response or None

    credits = mutasi_payload.get("credits", [])
    gaji_credits = [c for c in credits if c.get("category") == "Gaji"]

    # ---- Stage 3: verify ---------------------------------------------------
    await store.set_stage(job_id, "verify", "running")
    t0 = time.perf_counter()
    try:
        matches, verified_months = verify_slips_credits(slip_docs, gaji_credits)
    except Exception as exc:  # matcher is deterministic; guard defensively
        logger.exception("verify stage failed")
        matches, verified_months = [], set()
        audit.warnings.append(f"verification skipped: {exc}")
    timings["verify"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "verify", "completed")

    verification = VerificationInfo(
        matched_count=len(matches),
        verified_month_count=len(verified_months),
        matched_pairs=[_match_pair_view(p) for p in matches],
    )

    # ---- Stage 4: aggregate ------------------------------------------------
    await store.set_stage(job_id, "aggregate", "running")
    t0 = time.perf_counter()
    slip_total_paids = [
        float(d["total_paid"]) for d in slip_docs if d.get("total_paid") is not None
    ]
    income = compute_income(
        credits=credits,
        verified_months=verified_months,
        slip_total_paids=slip_total_paids,
        bonus_accept_pct=bonus_accept_pct,
    )
    timings["aggregate"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "aggregate", "completed")

    # ---- Stage 5: assemble -------------------------------------------------
    mutasi_accounts = [f.get("account", {}) for f in mut_files]
    name, name_source = resolve_applicant_name(
        slip_docs, mutasi_accounts, [sk_response] if sk_response else []
    )
    audit.stage_timings_ms = timings

    result = ApplicationResult(
        documents=doc_results,
        applicant=ApplicantInfo(name=name, name_source=name_source),
        income=income,
        verification=verification,
        audit=audit,
    )
    await store.set_result(job_id, result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_pipeline -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the whole suite so far**

Run: `python -m unittest discover -s ocr_orchestrator/tests -t . -v`
Expected: PASS (all tests from Tasks 1-9).

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/pipeline.py ocr_orchestrator/tests/test_pipeline.py
git commit -m "feat(orchestrator): five-stage pipeline orchestration"
```

---

## Task 10: FastAPI app (endpoints + async scheduling + /upload)

**Files:**
- Create: `ocr_orchestrator/api.py`
- Test: `ocr_orchestrator/tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

`ocr_orchestrator/tests/test_api.py`:
```python
import unittest
from unittest import mock

from fastapi.testclient import TestClient


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestApi(unittest.TestCase):
    def setUp(self):
        from ocr_orchestrator import api
        self.api = api
        self.client = TestClient(api.app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_root_redirects_to_upload(self):
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 307)
        self.assertEqual(r.headers["location"], "/upload")

    def test_post_requires_files(self):
        r = self.client.post("/api/v1/applications", files=[])
        self.assertIn(r.status_code, (400, 422))

    def test_get_unknown_job_404(self):
        r = self.client.get("/api/v1/applications/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_post_returns_202_and_job_is_retrievable(self):
        # Stub classify so the background task progresses without network.
        classify = _async([
            {"filename": "x.pdf", "document_type": "unknown", "confidence": "low"},
        ])
        with mock.patch.object(self.api.upstream, "classify_documents", classify):
            r = self.client.post(
                "/api/v1/applications",
                files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            )
            self.assertEqual(r.status_code, 202)
            body = r.json()
            self.assertIn("job_id", body)
            self.assertEqual(body["status_url"], f"/api/v1/applications/{body['job_id']}")
            # Job is retrievable; status is one of the valid states.
            g = self.client.get(body["status_url"])
            self.assertEqual(g.status_code, 200)
            self.assertIn(g.json()["status"],
                          {"pending", "running", "completed", "failed"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest ocr_orchestrator.tests.test_api -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.api'`.

- [ ] **Step 3: Write the implementation**

`ocr_orchestrator/api.py`:
```python
"""FastAPI surface for the orchestrator.

POST /api/v1/applications -> 202 + job_id (work runs in a background task).
GET  /api/v1/applications/{id} -> job status + result.
Plus /health, /upload (poll-based test page), and the OpenAPI 3.0.3 file-field
patch the sibling services use.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, RedirectResponse

from . import __version__, upstream
from .config import get_settings
from .jobs import JobStore
from .models import AcceptedResponse, JobStatusResponse
from .pipeline import run_job

logger = logging.getLogger("ocr_orchestrator.api")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="OCR Orchestrator",
    version=__version__,
    description=(
        "NILAM document-bundle orchestrator. Classifies an uploaded PDF pile, "
        "routes each document to the right OCR service, verifies slips against "
        "bank Gaji credits, and aggregates a monthly qualifying-income figure. "
        "Async job + polling."
    ),
)
app.openapi_version = "3.0.3"
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

store = JobStore(get_settings().job_retention)


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version,
                        openapi_version=app.openapi_version,
                        description=app.description, routes=app.routes)

    def rewrite(node: object) -> None:
        if isinstance(node, dict):
            if (node.get("type") == "string"
                    and node.get("contentMediaType") == "application/octet-stream"):
                node.pop("contentMediaType", None)
                node["format"] = "binary"
            for v in node.values():
                rewrite(v)
        elif isinstance(node, list):
            for item in node:
                rewrite(item)

    rewrite(schema)
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/upload", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post(
    "/api/v1/applications",
    response_model=AcceptedResponse,
    status_code=202,
    tags=["applications"],
    summary="Submit a document bundle; returns a job_id to poll",
)
async def create_application(
    files: List[UploadFile] = File(..., description="The unlabeled PDF bundle."),
    bonus_accept_pct: Optional[float] = Form(
        None, description="Analyst bonus-acceptance fraction 0.0-1.0 (default from config)."),
    password: Optional[str] = Form(None, description="Optional PDF password for protected files."),
) -> AcceptedResponse:
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one PDF.")
    if len(files) > settings.max_files:
        raise HTTPException(status_code=413,
                            detail=f"Too many files ({len(files)} > MAX_FILES={settings.max_files}).")

    payload: list[tuple[str, bytes]] = []
    for f in files:
        name = f.filename or "unnamed.pdf"
        if not (f.content_type in {"application/pdf", "application/octet-stream"}
                or name.lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail=f"{name!r}: not a PDF.")
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"{name!r}: empty upload.")
        payload.append((name, data))

    if bonus_accept_pct is None:
        pct = settings.default_bonus_accept_pct
    else:
        pct = max(0.0, min(1.0, bonus_accept_pct))  # clamp

    job = await store.create()
    task = asyncio.create_task(
        run_job(store, job.id, payload, bonus_accept_pct=pct, password=password)
    )
    task.add_done_callback(_log_task_result)
    await store.attach_task(job.id, task)

    return AcceptedResponse(
        job_id=job.id, status=job.status,
        status_url=f"/api/v1/applications/{job.id}",
    )


def _log_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("background job crashed: %r", exc)


@app.get(
    "/api/v1/applications/{job_id}",
    response_model=JobStatusResponse,
    tags=["applications"],
    summary="Poll a job's status and (when done) its result",
)
async def get_application(job_id: str) -> JobStatusResponse:
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return JobStatusResponse(
        job_id=job.id, status=job.status, stages=job.stages,
        result=job.result, error=job.error,
    )


_UPLOAD_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>OCR Orchestrator — Upload</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1a1a1a}
 .card{border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}
 label.drop{display:block;border:2px dashed #e5e7eb;border-radius:8px;padding:28px;text-align:center;cursor:pointer}
 label.drop.has{border-color:#059669;background:#f0fdf4}
 input[type=file]{display:none}
 .row{display:flex;gap:16px;align-items:center;margin-top:14px;flex-wrap:wrap}
 input[type=number],input[type=password]{padding:8px;border:1px solid #e5e7eb;border-radius:6px;font:inherit}
 button{font:inherit;font-weight:600;padding:10px 18px;border:none;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer}
 button:disabled{background:#94a3b8}
 #status{margin:10px 0;font-size:13px}
 pre{background:#0f172a;color:#e2e8f0;padding:16px;border-radius:6px;overflow:auto;font-size:12px;max-height:520px}
 .stages span{display:inline-block;padding:2px 8px;border-radius:4px;margin:2px;font-size:12px;background:#eef2ff;color:#3730a3}
</style></head><body>
<h1>OCR Orchestrator</h1>
<p>Upload the full document bundle (KTP, KK, SK, slip gaji, mutasi). The server
classifies each file, extracts what it can, and returns a monthly income figure.
&nbsp;·&nbsp; <a href="/docs">Swagger</a></p>
<form id="f" class="card">
 <label class="drop" id="drop" for="files"><span class="icon">📄</span>
   <div id="dl">Click to choose PDFs (multi-select)</div>
   <input type="file" id="files" name="files" accept="application/pdf,.pdf" multiple></label>
 <div class="row">
   <label>Bonus accept %: <input type="number" id="pct" min="0" max="100" step="1" value="0" style="width:80px"></label>
   <label>PDF password: <input type="password" id="pw" placeholder="optional"></label>
   <button type="submit" id="go">Submit</button>
 </div>
 <div id="status"></div>
 <div class="stages" id="stages"></div>
</form>
<pre id="out">(no request sent yet)</pre>
<script>
const f=document.getElementById('f'),fi=document.getElementById('files'),drop=document.getElementById('drop'),
 dl=document.getElementById('dl'),st=document.getElementById('status'),out=document.getElementById('out'),
 go=document.getElementById('go'),stages=document.getElementById('stages');
fi.addEventListener('change',()=>{if(fi.files.length){drop.classList.add('has');dl.textContent=fi.files.length+' file(s) selected';}});
function renderStages(s){stages.innerHTML=(s||[]).map(x=>`<span>${x.name}: ${x.status}</span>`).join('');}
async function poll(url){
 for(let i=0;i<600;i++){
   const r=await fetch(url);const d=await r.json();
   renderStages(d.stages);out.textContent=JSON.stringify(d,null,2);
   if(d.status==='completed'||d.status==='failed'){st.textContent='Status: '+d.status;return;}
   st.textContent='Status: '+d.status+' …';await new Promise(z=>setTimeout(z,1000));
 }
}
f.addEventListener('submit',async e=>{e.preventDefault();
 if(!fi.files.length){st.textContent='Pick at least one PDF.';return;}
 const fd=new FormData();for(const x of fi.files)fd.append('files',x,x.name);
 fd.append('bonus_accept_pct',(Number(document.getElementById('pct').value)||0)/100);
 const pw=document.getElementById('pw').value;if(pw)fd.append('password',pw);
 go.disabled=true;st.textContent='Submitting…';stages.innerHTML='';
 try{
   const r=await fetch('/api/v1/applications',{method:'POST',body:fd});
   const d=await r.json();
   if(r.status!==202){st.textContent='HTTP '+r.status+' — '+(d.detail||'error');out.textContent=JSON.stringify(d,null,2);return;}
   st.textContent='Accepted — polling…';await poll(d.status_url);
 }catch(err){st.textContent='Network error: '+err;}finally{go.disabled=false;}
});
</script></body></html>"""


@app.get("/upload", response_class=HTMLResponse, include_in_schema=False)
def upload_page() -> HTMLResponse:
    return HTMLResponse(_UPLOAD_PAGE)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest ocr_orchestrator.tests.test_api -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/api.py ocr_orchestrator/tests/test_api.py
git commit -m "feat(orchestrator): FastAPI endpoints + async scheduling + upload page"
```

---

## Task 11: Deployment scaffolding (run script, Docker, compose, env, README)

**Files:**
- Create: `ocr_orchestrator/run_api.sh`
- Create: `ocr_orchestrator/Dockerfile`
- Create: `ocr_orchestrator/README.md`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Write `run_api.sh`**

`ocr_orchestrator/run_api.sh`:
```bash
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
```

- [ ] **Step 2: Write `Dockerfile`**

`ocr_orchestrator/Dockerfile`:
```dockerfile
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
```

- [ ] **Step 3: Add the service to `docker-compose.yml`**

Append this service under `services:` in `docker-compose.yml` (after `ocr_match`):
```yaml
  ocr_orchestrator:
    build: { context: ., dockerfile: ocr_orchestrator/Dockerfile }
    image: ocr_orchestrator
    container_name: ocr_orchestrator
    ports: ["8500:8500"]
    env_file: [.env]
    # Reach the upstream services by their compose DNS names, not 127.0.0.1.
    environment:
      - OCR_CLASSIFIER_URL=http://ocr_classifier:8000
      - OCR_SK_URL=http://ocr_sk:8100
      - OCR_SLIP_URL=http://ocr_slip:8200
      - OCR_MUTASI_URL=http://ocr_mutasi:8300
    depends_on: [ocr_classifier, ocr_sk, ocr_slip, ocr_mutasi]
    restart: unless-stopped
```

- [ ] **Step 4: Add orchestrator vars to `.env.example`**

Append to `.env.example`:
```dotenv

# --- ocr_orchestrator (port 8500) ---
# Fans out to the four services above; reuses their OCR_*_URL registry entries.
# Tunables (defaults shown):
# UPSTREAM_TIMEOUT_S=180          # generous — covers the slow mutasi batch parse
# DEFAULT_BONUS_ACCEPT_PCT=0.0    # analyst bonus-acceptance fraction (0..1)
# JOB_RETENTION=200               # most-recent in-memory jobs kept
OCR_ORCHESTRATOR_URL=http://127.0.0.1:8500
```

- [ ] **Step 5: Write `README.md`**

`ocr_orchestrator/README.md`:
```markdown
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
```

- [ ] **Step 6: Make `run_api.sh` executable and validate compose**

Run:
```bash
git update-index --chmod=+x ocr_orchestrator/run_api.sh 2>/dev/null || true
docker compose config >/dev/null && echo "compose OK"
```
Expected: `compose OK` (validates the new service block parses). If Docker isn't installed locally, skip this check — CI/compose host will catch it.

- [ ] **Step 7: Commit**

```bash
git add ocr_orchestrator/run_api.sh ocr_orchestrator/Dockerfile ocr_orchestrator/README.md docker-compose.yml .env.example
git commit -m "feat(orchestrator): deployment scaffolding (run script, Docker, compose, env, README)"
```

---

## Task 12: Full-suite green + manual smoke + self-review

**Files:**
- Create: `ocr_orchestrator/smoke_orchestrator.py`

- [ ] **Step 1: Run the entire test suite**

Run: `python -m unittest discover -s ocr_orchestrator/tests -t . -v`
Expected: PASS — all tests across Tasks 1-10 (config, models, income, jobs, routing, verify, identity, pipeline, api).

- [ ] **Step 2: Write a manual smoke script**

`ocr_orchestrator/smoke_orchestrator.py`:
```python
"""Manual end-to-end smoke test (NEEDS the four OCR services running + .env).

Usage (from repo root, with venv active and services up):
    python ocr_orchestrator/smoke_orchestrator.py path/to/*.pdf

Submits the bundle, polls until done, prints the income breakdown.
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8500"


def main(paths: list[str]) -> int:
    if not paths:
        print("Pass at least one PDF path.")
        return 2
    files = [("files", (p.split("/")[-1].split("\\")[-1], open(p, "rb"), "application/pdf"))
             for p in paths]
    r = httpx.post(f"{BASE}/api/v1/applications",
                   files=files, data={"bonus_accept_pct": "0.5"}, timeout=60)
    print("POST", r.status_code, r.json())
    if r.status_code != 202:
        return 1
    status_url = BASE + r.json()["status_url"]
    for _ in range(600):
        g = httpx.get(status_url, timeout=30).json()
        if g["status"] in ("completed", "failed"):
            print("FINAL status:", g["status"])
            if g.get("result"):
                print("income:", g["result"]["income"])
                print("applicant:", g["result"]["applicant"])
                print("audit:", g["result"]["audit"])
            else:
                print("error:", g.get("error"))
            return 0 if g["status"] == "completed" else 1
        time.sleep(1)
    print("timed out waiting for job")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 3: (Optional, networked) Run the smoke test**

Only if the four services + `.env` are available. Start the orchestrator
(`.venv/Scripts/uvicorn ocr_orchestrator.api:app --port 8500`) and run:
```bash
python ocr_orchestrator/smoke_orchestrator.py sample_ktp.pdf sample_slip.pdf mutasi_*.pdf
```
Expected: `FINAL status: completed` and an `income` block with a `basis` of
`bank_verified` (or `slip_fallback` if no mutasi). If services aren't running,
skip — the unit suite already covers the logic.

- [ ] **Step 4: Plan self-review against the spec**

Confirm each spec section maps to a task (see coverage table at the bottom of
this plan). No code changes expected here unless a gap is found.

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/smoke_orchestrator.py
git commit -m "feat(orchestrator): manual end-to-end smoke script"
```

---

## Self-Review (author's check against the spec)

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §4 service shape / modules | T1 (config), T2 (models), T5 (upstream), T11 (scaffolding) |
| §4 config keys (`UPSTREAM_TIMEOUT_S`, `DEFAULT_BONUS_ACCEPT_PCT`, `JOB_RETENTION`, URLs) | T1, T11 (.env.example) |
| §5 POST 202 + validation (400/413) | T10 |
| §5 GET status/result + 404 | T10 |
| §5 in-memory job store, single-worker, retention | T4, T11 (notes in run_api.sh/Dockerfile) |
| §6 Stage 1 classify + bucket | T6, T9 |
| §6 Stage 2 extract (concurrent, ktp/kk recorded, unknown warned) | T6 (status), T9 (extract) |
| §6 Stage 3 verify (imported matcher) | T7, T9 |
| §6 Stage 4 aggregate | T3, T9 |
| §6 Stage 5 assemble + `applicant` block + name resolution | T8, T9 |
| §7 income formula + 4 `basis` levels + n_months + THR/12 + bonus pct | T3 |
| §8 error handling (classifier-down fails; extractor-down degrades; clamp pct) | T9 (pipeline), T10 (clamp/validation) |
| §9 testing (income, routing, pipeline-mocked, jobs) | T3, T4, T6, T9 + smoke T12 |
| §10 out-of-scope (no FMV/decision/frontend/joint/ktp-kk-extraction) | respected — none implemented |
| §11 success criteria | T9 happy-path + degrade tests; T12 smoke |

**Type consistency:** `compute_income(...) -> IncomeBreakdown` (T3) is consumed in T9; `route_documents(...) -> (Buckets, list[DocumentResult], list[str])` (T6) consumed in T9; `verify_slips_credits(...) -> (matches, set[str])` (T7) consumed in T9; `resolve_applicant_name(...) -> (name, source)` (T8) consumed in T9; `JobStore` methods (T4) used in T9/T10; model field names (T2) used throughout. Upstream function names (`classify_documents`, `parse_slips`, `extract_mutations`, `parse_sk`) are consistent between T5 and the T9 mocks.

**Placeholder scan:** none — every step ships runnable code/commands.

---

## Notes / known risks for the implementer

- **`ocr_match` import requires Azure env at matcher *call* time.** `verify.py` imports are safe, but `match_all()` calls `ocr_match.config.get_settings()`, which validates `AZURE_OPENAI_*`. Tests patch `ocr_match.matcher.get_settings`; in real runs the shared `.env` provides the keys. The orchestrator's own `config.py` deliberately omits Azure keys so it can start/test without them — but the running process still needs them in `.env` for the verify stage.
- **Classifier result ↔ file pairing is by filename.** If two uploaded PDFs share a filename, `route_documents` maps both to the same bytes. Acceptable for v1; note it if duplicate filenames are expected.
- **`extract_mutations` returns the full batch payload** (not Gaji-only like `ocr_match`) because income needs every category and `files[].account.nama`.
- **Single worker only** (in-memory store) — enforced by convention, noted in `run_api.sh`/`Dockerfile`/README.
- **TestClient + background task:** `test_api` asserts the 202 + retrievability, not full completion (which the deterministic `test_pipeline` covers) to avoid event-loop timing flakiness.
```
