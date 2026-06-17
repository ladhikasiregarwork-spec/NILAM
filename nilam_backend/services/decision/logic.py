"""Final decision / summary synthesis (backend_info.md §19).

Pure function over already-computed inputs: capacity (10), the chosen offering's
installment (12), and the credit score (13). The prototype's SummaryDecisionCard
leaves the approve/reject click to the analyst, so it defines no auto-decision
formula — only the affordability rule `angsuranKpr <= kemampuan`. This service
combines that rule with the credit-score grade bands (the only policy signal the
prototype encodes: 80 / 65 / 50) into a recommendation:

    margin = kemampuanBayar - angsuranKpr        (>= 0 -> affordable)
    not affordable                 -> rejected   (installment beyond DIR ceiling)
    affordable & score >= 65 (A/B) -> approved
    affordable & 50 <= score < 65  -> review     (refer to analyst)
    affordable & score < 50  (D)   -> rejected
"""

from typing import List


def build_decision(
    kemampuan_bayar: float,
    angsuran_kpr: float,
    score: int,
    grade: str,
) -> dict:
    margin = int(kemampuan_bayar - angsuran_kpr)
    affordable = margin >= 0
    reasons: List[str] = []

    if affordable:
        reasons.append(
            "Angsuran KPR ({}) dalam batas kemampuan bayar ({}); margin {}.".format(
                int(angsuran_kpr), int(kemampuan_bayar), margin
            )
        )
    else:
        reasons.append(
            "Angsuran KPR ({}) melebihi kemampuan bayar ({}); margin {}.".format(
                int(angsuran_kpr), int(kemampuan_bayar), margin
            )
        )

    if not affordable:
        decision = "rejected"
        reasons.append("Ditolak: angsuran melampaui batas kemampuan (DIR).")
    elif score >= 65:
        decision = "approved"
        reasons.append("Credit score {} ({}) memenuhi ambang persetujuan (>=65).".format(score, grade))
    elif score >= 50:
        decision = "review"
        reasons.append("Credit score {} ({}) pada rentang tinjauan analis (50-64).".format(score, grade))
    else:
        decision = "rejected"
        reasons.append("Credit score {} ({}) di bawah ambang minimum (<50).".format(score, grade))

    return {
        "decision": decision,
        "kemampuanBayar": int(kemampuan_bayar),
        "angsuranKpr": int(angsuran_kpr),
        "marginKemampuan": margin,
        "score": score,
        "grade": grade,
        "reasons": reasons,
    }
