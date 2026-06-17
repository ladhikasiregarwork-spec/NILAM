"""Assemble the UI-shaped ApplicationView (the dashboard payload).

The prototype has no single ApplicationView type — the dashboard cards read
slices of the flow state. This bundles every stage's result into one object the
BFF/dashboard can render, mirroring those slices (identity, SLIK, income/THP,
capacity, collateral plafond, offering, credit score, fraud, coverage, matching,
decision, survey).
"""

from typing import Any, Optional


def assemble_application_view(
    *,
    app_id: str,
    uploads: Any,
    ocr: Any,
    coverage: Any,
    fraud: Any,
    identity: Any,
    slik: Any,
    income: Any,
    capacity: Any,
    matching: Any,
    agunan: Any,
    npw: Optional[float],
    financials: dict,
    survey: dict,
) -> dict:
    return {
        "applicationId": app_id,
        "uploads": uploads,
        "ocr": ocr,
        "coverage": coverage,
        "fraud": fraud,
        "identity": identity,
        "slik": slik,
        "income": income,            # {nasabah, pasangan?, total}
        "capacity": capacity,        # {penghasilanBulanan, dirRate, kemampuanBayar}
        "agunan": agunan,
        "npw": npw,
        "plafond": financials.get("plafond"),
        "offering": financials.get("offering"),
        "creditScore": financials.get("creditScore"),
        "matching": matching,        # {monthlyRecap, incomeTransactions}
        "decision": financials.get("decision"),
        "survey": survey,            # {status, surveyValue?, surveyNote?}
    }
