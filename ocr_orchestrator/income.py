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
