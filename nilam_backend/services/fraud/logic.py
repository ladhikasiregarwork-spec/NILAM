"""Fraud detection (stub). Mirrors `data/fraudFixtures.ts` FRAUD_RESULT.

The prototype's `engines/fraud/fraudEngine.ts` was emptied and superseded by a
fixture; backend_info.md §14 marks this a stub. It returns deterministic
per-check scores and an overall figure regardless of input, so the dashboard's
fraud card renders. Real slip/mutasi/identity cross-checks land here later.
"""

from typing import Any, Optional

CHECKS = [
    {"name": "Slip Gaji Authentic", "score": 0.95},
    {"name": "Mutasi Valid (12 Bulan)", "score": 0.93},
    {"name": "Consistency Check", "score": 0.96},
    {"name": "Pattern Analysis", "score": 0.91},
]
OVERALL = 0.94


def detect_fraud(slip: Optional[Any] = None, mutasi: Optional[Any] = None, identity: Optional[Any] = None) -> dict:
    return {"checks": [dict(c) for c in CHECKS], "overall": OVERALL}
