"""Pure YYYY-MM derivation for slips and credits — local copy of the helpers that
used to live in ``ocr_match.pipeline``. Kept here so the orchestrator imports
nothing from ``ocr_match``. This is slip *placement* logic, not matching.
"""
from __future__ import annotations

import re
from typing import Any, Optional

_MONTHS = {
    "JAN": 1, "JANUARI": 1,
    "FEB": 2, "FEBRUARI": 2,
    "MAR": 3, "MARET": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5, "MEI": 5,
    "JUN": 6, "JUNI": 6, "JUNE": 6,
    "JUL": 7, "JULI": 7, "JULY": 7,
    "AUG": 8, "AGT": 8, "AGUSTUS": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OKT": 10, "OKTOBER": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DES": 12, "DESEMBER": 12, "DECEMBER": 12,
}

# Boundary is letter-only — ``(?<![A-Za-z])``/``(?![A-Za-z])`` rather than ``\b`` —
# so a month token glued to an underscore parses (e.g. ``Slip_Februari_2025.pdf``).
# This deliberately differs from ocr_match.pipeline's ``\b`` original (``_`` is a
# word char, so ``\b`` would reject the common underscore-delimited filenames). It
# only affects placement of *unmatched* slips, so the slight divergence is safe.
_MONTH_NAME_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")(?![A-Za-z])[\s_/-]*(\d{4})",
    re.IGNORECASE,
)


def slip_month(slip: dict[str, Any]) -> Optional[str]:
    """Best-effort YYYY-MM for a slip dict: ``period`` first, then filename."""
    period = slip.get("period")
    if isinstance(period, str) and period:
        return period
    name = slip.get("source_file") or ""
    m = _MONTH_NAME_RE.search(name)
    if m:
        mon = _MONTHS[m.group(1).upper()]
        year = int(m.group(2))
        return f"{year:04d}-{mon:02d}"
    m2 = re.search(r"(\d{4})[-_/](\d{2})", name)
    if m2:
        return f"{int(m2.group(1)):04d}-{int(m2.group(2)):02d}"
    return None


def credit_month(tanggal: Any) -> Optional[str]:
    """Credits use ISO ``YYYY-MM-DD``; slice off the day."""
    if isinstance(tanggal, str) and len(tanggal) >= 7:
        return tanggal[:7]
    return None
