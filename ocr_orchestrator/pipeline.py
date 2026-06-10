"""Async stage orchestration: classify -> extract -> verify -> aggregate ->
fmv -> decide -> assemble. The six tracked stages (classify, extract, verify,
aggregate, fmv, decide) are surfaced in ``job.stages``; assemble is the final
(untracked) completion step. Updates the job's stages as it progresses.

Imported as ``from . import upstream`` so tests can patch the upstream calls.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from . import upstream
from .config import get_settings
from .decision import decide
from .identity import resolve_applicant_name
from .income import compute_income
from .jobs import JobStore
from .monthly import build_monthly_breakdown
from .models import (
    ApplicantInfo,
    ApplicationResult,
    CollateralInput,
    FmvResult,
    LoanRequest,
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


def _slip_base(source_file: Any) -> str:
    """Recover the uploaded basename from ocr_slip's rewritten ``source_file``.

    ocr_slip emits ``source_file`` as a full path (parser) or
    ``name#page-N#date`` (LLM fallback), never the bare uploaded filename, so we
    strip any directory and any ``#`` suffix to join the extraction back to its
    DocumentResult.
    """
    return os.path.basename(str(source_file or "")).split("#", 1)[0]


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
    """Run the pipeline, guaranteeing the job ends ``completed`` or ``failed``.

    ``_execute`` already handles a classifier outage (fail) and extractor
    outages (degrade). This wrapper is the backstop: any *unexpected* exception
    in an unguarded stage is turned into a failed job rather than leaving it
    stuck in ``running``.
    """
    try:
        await _execute(
            store, job_id, files,
            bonus_accept_pct=bonus_accept_pct, password=password,
            collateral=collateral, loan=loan, input_warnings=input_warnings,
        )
    except Exception as exc:  # backstop — pipeline stages are mostly pure
        logger.exception("run_job crashed for job %s", job_id)
        await store.fail(job_id, f"internal error: {exc}")


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
    """Run the whole pipeline for one job, mutating job state in ``store``."""
    timings: dict[str, float] = {}
    audit = OrchestratorAudit()
    if input_warnings:
        audit.warnings.extend(input_warnings)
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
    slip_by_file: dict[str, dict[str, Any]] = {}
    for _d in slip_docs:
        slip_by_file.setdefault(_slip_base(_d.get("source_file")), _d)
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
    income.monthly_breakdown = build_monthly_breakdown(credits, slip_docs, matches)
    timings["aggregate"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "aggregate", "completed")

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

    # ---- Stage 7: assemble -------------------------------------------------
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
        collateral=collateral,
        loan=loan,
        fmv=fmv_result,
        decision=decision_result,
        audit=audit,
    )
    await store.set_result(job_id, result)
