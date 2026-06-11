"""Adapt an ocr_match /api/v1/match response into what the pipeline consumes.

ocr_match is the single front door: its response carries full slip extraction,
full mutasi extraction (all categories + account/files), and the slip<->Gaji match
result. This module reads that JSON and returns plain dicts + local MatchView
objects — it imports nothing from ocr_match.
"""
from __future__ import annotations

from typing import Any

from .models import MatchedCreditView, MatchedSlipView, MatchView
from .slip_dates import credit_month


def parse_match_response(
    payload: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict], list[MatchView], set[str]]:
    """Return ``(slip_docs, credits, mut_files, matches, verified_months)``.

    - ``slip_docs``: every parsed slip dict (``slip_extraction.documents``).
    - ``credits``: every mutasi credit dict, ALL categories
      (``mutasi_extraction.credits``).
    - ``mut_files``: mutasi per-file dicts incl. ``account`` (``mutasi_extraction.files``).
    - ``matches``: local ``MatchView`` list.
    - ``verified_months``: YYYY-MM buckets that produced a match.
    """
    slip_extraction = payload.get("slip_extraction") or {}
    mutasi_extraction = payload.get("mutasi_extraction") or {}

    slip_docs = list(slip_extraction.get("documents") or [])
    credits = list(mutasi_extraction.get("credits") or [])
    mut_files = list(mutasi_extraction.get("files") or [])

    matches: list[MatchView] = []
    verified_months: set[str] = set()
    for m in payload.get("matches") or []:
        slip = m.get("slip") or {}
        credit = m.get("credit") or {}
        month = credit.get("month") or credit_month(credit.get("tanggal"))
        matches.append(MatchView(
            slip=MatchedSlipView(source_file=slip.get("source_file")),
            credit=MatchedCreditView(
                month=month,
                tanggal=credit.get("tanggal"),
                amount=credit.get("amount"),
            ),
            match_pattern=m.get("match_pattern"),
        ))
        if month:
            verified_months.add(month)

    return slip_docs, credits, mut_files, matches, verified_months
