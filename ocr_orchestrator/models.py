"""Pydantic request/response/job types for the orchestrator.

These double as FastAPI response schemas. ``extracted`` and ``matched_pairs``
hold loosely-typed upstream payloads, so they are plain dicts.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

JobState = Literal["pending", "running", "completed", "failed"]
StageState = Literal["pending", "running", "completed", "failed", "skipped"]
DocStatus = Literal["extracted", "recognized_not_extracted", "unclassified"]
IncomeBasis = Literal["bank_verified", "bank_unverified", "slip_fallback", "none"]
RowSource = Literal["bank_verified", "bank_unverified", "bank_only", "slip_only"]
DecisionRecommendation = Literal["eligible", "not_eligible", "refer_to_analyst"]


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


class MonthlyIncomeRow(BaseModel):
    """One calendar month of income, joined from bank credits + a salary slip.

    Bank-first (spec §3): bank credits are the source of truth for the income
    amounts; the matched slip supplies ``deduction``/``total_paid``.

    NOTE: ``bonus_non_fixed`` intentionally includes bank ``Insentif`` (spec §3,
    decision 4). This differs from the aggregate ``IncomeBreakdown``, which counts
    Insentif AS salary (``avg_monthly(Gaji + Insentif)``). The two views serve
    different purposes and are allowed to diverge — do not "fix" this.

    ``null`` means "no data source for this field"; ``0`` means "a source covered
    it and the amount was zero" (e.g. a normal no-THR month on a bank row shows
    ``thr == 0``, not ``null``).
    """
    month: str                              # "YYYY-MM" — the "month payment" key
    fixed_routine_income: Optional[float]   # bank Gaji   (slip pokok if slip_only)
    thr: Optional[float]                    # bank THR    (null if slip_only)
    bonus_non_fixed: Optional[float]        # bank Bonus + Insentif (slip incentive if slip_only)
    deduction: Optional[float]              # slip only
    total_paid: Optional[float]             # slip only
    bank_salary_credit: Optional[float]     # bank Gaji credit amount (null if slip_only)
    source: RowSource


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
    monthly_breakdown: list[MonthlyIncomeRow] = Field(default_factory=list)


class VerificationInfo(BaseModel):
    """Summary of the slip<->Gaji verification."""
    matched_count: int = 0
    verified_month_count: int = 0
    matched_pairs: list[dict[str, Any]] = Field(default_factory=list)


class MatchedSlipView(BaseModel):
    """The only slip field downstream code reads off a match pair."""
    source_file: Optional[str] = None


class MatchedCreditView(BaseModel):
    """The only credit fields downstream code reads off a match pair."""
    month: Optional[str] = None
    tanggal: Optional[str] = None
    amount: Optional[float] = None


class MatchView(BaseModel):
    """Local, ocr_match-free view of one matched slip<->credit pair.

    Replaces ``ocr_match.models.MatchPair`` for the orchestrator's purposes:
    ``monthly.build_monthly_breakdown`` reads ``.slip.source_file`` and
    ``.credit.month``; ``pipeline._match_pair_view`` also reads ``.credit.tanggal``,
    ``.credit.amount`` and ``.match_pattern``.
    """
    slip: MatchedSlipView = Field(default_factory=MatchedSlipView)
    credit: MatchedCreditView = Field(default_factory=MatchedCreditView)
    match_pattern: Optional[str] = None


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


class OrchestratorAudit(BaseModel):
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
    classifier_errors: list[str] = Field(default_factory=list)
    extractor_errors: list[str] = Field(default_factory=list)
    fmv_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
