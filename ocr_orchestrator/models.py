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
