"""Pure per-month income breakdown (spec §4–§6).

Joins the mutasi ``credits[]`` and slip ``documents[]`` the pipeline already
fetched, keyed by month, into one ``MonthlyIncomeRow`` per month (union of bank
salary-credit months and slip-period months). Bank-first: bank credits are the
source of truth for the income amounts; the matched slip supplies
``deduction``/``total_paid``. No I/O — mirrors ``income.py``/``verify.py``.

Reuses ``slip_dates.slip_month`` (the non-trivial month derivation: slip ``period``
then filename parsing). Credit months are the same ``tanggal[:7]`` slice
``income.py`` uses.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from .slip_dates import slip_month as _slip_month

from .models import MonthlyIncomeRow

# Bank credit categories that count as salary-type (a row-creating signal).
# 'Lainnya' is excluded — it never creates a month on its own (spec §6).
_FIXED = "Gaji"
_THR = "THR"
_NON_FIXED = ("Bonus", "Insentif")
_SALARY_TYPE = (_FIXED, _THR) + _NON_FIXED


def _f(value: Any) -> float:
    """Coerce a possibly-None/str amount to float; None -> 0.0."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _credit_month(tanggal: Any) -> Optional[str]:
    """Same slice income.py uses: ISO 'YYYY-MM-DD' -> 'YYYY-MM'."""
    if isinstance(tanggal, str) and len(tanggal) >= 7:
        return tanggal[:7]
    return None


def build_monthly_breakdown(
    credits: list[dict[str, Any]],
    slip_docs: list[dict[str, Any]],
    matches: list,
) -> list[MonthlyIncomeRow]:
    """Build the per-month income table (spec §6).

    Args:
        credits: every mutasi credit dict (all categories) with ``category``,
            ``amount``, ``tanggal`` (ISO ``YYYY-MM-DD``).
        slip_docs: ocr_slip ``documents[]`` dicts.
        matches: ``MatchPair``-like list from the verify stage. Only
            ``pair.slip.source_file`` and ``pair.credit.month`` are read.

    Returns:
        ``MonthlyIncomeRow`` list sorted ascending by ``month``.
    """
    # --- bank side: sum salary-type credits per month -----------------------
    bank: dict[str, dict[str, float]] = {}
    for c in credits:
        category = c.get("category")
        if category not in _SALARY_TYPE:
            continue                       # 'Lainnya'/None never create a month
        month = _credit_month(c.get("tanggal"))
        if not month:
            continue
        b = bank.setdefault(month, {"gaji": 0.0, "thr": 0.0, "bonus": 0.0})
        amount = _f(c.get("amount"))
        if category == _FIXED:
            b["gaji"] += amount
        elif category == _THR:
            b["thr"] += amount
        else:                              # Bonus or Insentif
            b["bonus"] += amount

    # --- which slips matched, and to which bank month -----------------------
    matched_home: dict[str, str] = {}      # slip source_file -> bank credit month
    for pair in matches:
        source_file = pair.slip.source_file
        credit_month = pair.credit.month
        if source_file and credit_month:
            matched_home[source_file] = credit_month

    # --- slip side: home each slip and accumulate ---------------------------
    slip: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"deduction": 0.0, "total_paid": 0.0,
                 "pokok": 0.0, "incentive": 0.0, "matched": False}
    )
    for d in slip_docs:
        source_file = d.get("source_file")
        if source_file in matched_home:
            home = matched_home[source_file]
            is_matched = True
        else:
            home = _slip_month(d)
            is_matched = False
        if not home:
            continue                       # un-placeable slip (no month) is dropped
        s = slip[home]
        s["deduction"] += _f(d.get("deduction"))
        s["total_paid"] += _f(d.get("total_paid"))
        s["pokok"] += _f(d.get("pokok"))
        s["incentive"] += _f(d.get("incentive"))
        s["matched"] = s["matched"] or is_matched

    # --- assemble one row per month (union), sorted -------------------------
    rows: list[MonthlyIncomeRow] = []
    for month in sorted(set(bank) | set(slip)):
        b = bank.get(month)
        s = slip.get(month)
        if b is not None:
            # bank row: bank-sourced fields are real sums (0 when absent)
            if s is not None:
                source = "bank_verified" if s["matched"] else "bank_unverified"
                deduction = s["deduction"]
                total_paid = s["total_paid"]
            else:
                source = "bank_only"
                deduction = None
                total_paid = None
            rows.append(MonthlyIncomeRow(
                month=month,
                fixed_routine_income=b["gaji"],
                thr=b["thr"],
                bonus_non_fixed=b["bonus"],
                deduction=deduction,
                total_paid=total_paid,
                bank_salary_credit=b["gaji"],
                source=source,
            ))
        else:
            # slip_only row: no bank data -> thr / bank_salary_credit null
            rows.append(MonthlyIncomeRow(
                month=month,
                fixed_routine_income=s["pokok"],
                thr=None,
                bonus_non_fixed=s["incentive"],
                deduction=s["deduction"],
                total_paid=s["total_paid"],
                bank_salary_credit=None,
                source="slip_only",
            ))
    return rows
