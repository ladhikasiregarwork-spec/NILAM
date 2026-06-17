from typing import Optional

from nilam_backend.core.money import js_round


def max_plafond(angsuran: float, annual_rate: float, months: int) -> int:
    """Largest principal whose monthly annuity <= angsuran at the given rate/months."""
    if angsuran <= 0 or months <= 0:
        return 0
    im = annual_rate / 12
    if im == 0:
        return js_round(angsuran * months)
    return js_round((angsuran * (1 - (1 + im) ** (-months))) / im)


def anuitas(principal: float, annual_rate: float, months: int) -> int:
    """Monthly annuity installment for a principal at an annual rate over N months."""
    if months <= 0 or principal <= 0:
        return 0
    im = annual_rate / 12
    if im == 0:
        return js_round(principal / months)
    return js_round((principal * im) / (1 - (1 + im) ** (-months)))


def max_tenor_by_age(age: Optional[int] = None, retirement_age: int = 56, cap: int = 25) -> int:
    """Max KPR tenor (years): loan must finish by retirement age, capped at `cap`."""
    if age is None:
        return cap
    return max(1, min(cap, retirement_age - age))


def _sisa_saldo(principal: float, annual_rate: float, total_months: int, paid_months: int) -> float:
    """Outstanding balance after `paid_months` of an annuity over `total_months`."""
    im = annual_rate / 12
    if im == 0:
        return max(0.0, principal - (principal / total_months) * paid_months)
    a = (principal * im) / (1 - (1 + im) ** (-total_months))
    f = (1 + im) ** paid_months
    return max(0.0, principal * f - a * ((f - 1) / im))


def build_schedule(plafon: float, tenor_years: int, periods: list[dict]) -> list[dict]:
    """Installment schedule for a fixed-then-floating/tiered KPR. At each rate change
    the annuity is recomputed on the OUTSTANDING balance over the REMAINING tenor."""
    balance = plafon
    cursor = 0  # years elapsed
    out: list[dict] = []
    for p in periods:
        rem_months = (tenor_years - cursor) * 12
        if rem_months <= 0 or balance <= 0:
            break
        p_years = (tenor_years - cursor) if p["years"] is None else min(p["years"], tenor_years - cursor)
        if p_years <= 0:
            break
        out.append(
            {
                "fromYear": cursor + 1,
                "toYear": cursor + p_years,
                "years": p_years,
                "rate": p["rate"],
                "angsuran": anuitas(balance, p["rate"], rem_months),
                "floating": p["rate"] >= 0.12,
            }
        )
        balance = _sisa_saldo(balance, p["rate"], rem_months, p_years * 12)
        cursor += p_years
    return out
