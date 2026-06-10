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
