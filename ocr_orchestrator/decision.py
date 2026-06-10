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
