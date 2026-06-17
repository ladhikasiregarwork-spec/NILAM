"""ocr_match (:5005) -> normalized match pairs.

Verification finding (spec §3): ocr_match returns matched slip<->credit PAIRS +
raw lists, NOT the UI's MatchTxn[]/MonthlyRecap[]. The UI monthly recap is built
server-side by `projection/matching.py`; this client only flattens the pairs +
audit to camelCase for orchestration/diagnostics.
"""

from typing import Any

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_json


def normalize_match(raw: dict) -> dict:
    pairs = []
    for m in raw.get("matches", []) or []:
        slip = m.get("slip", {}) or {}
        credit = m.get("credit", {}) or {}
        pairs.append({
            "slipFile": slip.get("source_file"),
            "creditTanggal": credit.get("tanggal"),
            "amount": credit.get("amount"),
            "category": credit.get("category"),
            "confidence": m.get("confidence"),
            "reason": m.get("reason"),
            "amountDiffRp": m.get("amount_diff_rp"),
            "amountDiffPct": m.get("amount_diff_pct"),
            "daysOff": m.get("days_off"),
            "matchPattern": m.get("match_pattern"),
        })
    audit = raw.get("audit", {}) or {}
    return {
        "pairs": pairs,
        "matchedCount": audit.get("matched_count", len(pairs)),
        "monthsProcessed": audit.get("months_processed", []) or [],
    }


async def fetch_match(payload: Any) -> dict:
    s = get_settings()
    raw = await post_json("{}/api/v1/match".format(s.match_url), json=payload, service="match")
    return normalize_match(raw)
