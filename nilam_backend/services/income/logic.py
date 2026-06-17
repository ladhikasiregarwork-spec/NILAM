"""Income / THP engine. Port of `engines/income/incomeExtractionEngine.ts`
(component extraction) + `engines/thp/thpEngine.ts` (take-home synthesis).

The TS `extractIncome` consumes pre-aggregated per-key buckets (`OcrMutasiResult`).
Here the input is a `MutasiExtract` (the contract in backend_info.md §9), so this
module first aggregates the classified credit transactions into the same
`{count, sum, min}` buckets, then applies the identical component + THP formulas.
THR/bonus come from the mutasi classification (design decision), not the slip.
"""

from typing import List, Optional

from nilam_backend.core.money import js_round
from nilam_backend.domain.documents import MutasiExtract
from nilam_backend.domain.income import IncomeComponent

KEYS = ["Gaji", "THR", "Bonus", "Insentif"]


def aggregate_buckets(mutasi: MutasiExtract) -> dict:
    """Sum classified credit transactions into per-key {count, sum, min} buckets."""
    buckets = {k: {"count": 0, "sum": 0.0, "min": None} for k in KEYS}
    for t in mutasi.transactions:
        if t.dk != "Kredit":
            continue
        b = buckets.get(t.klasifikasi)
        if b is None:
            continue
        b["count"] += 1
        b["sum"] += t.nominal
        b["min"] = t.nominal if b["min"] is None else min(b["min"], t.nominal)
    return buckets


def extract_components(mutasi: MutasiExtract) -> List[IncomeComponent]:
    """One component per key: avg = round(sum/count), min, mode=avg, weight=1."""
    buckets = aggregate_buckets(mutasi)
    out: List[IncomeComponent] = []
    for k in KEYS:
        b = buckets[k]
        avg = js_round(b["sum"] / b["count"]) if b["count"] else 0
        mn = js_round(b["min"]) if b["min"] is not None else 0
        out.append(IncomeComponent(key=k, avg=avg, min=mn, mode="avg", weight=1))
    return out


def adjusted(c: IncomeComponent) -> int:
    """Weighted component value (TS thpEngine.adjusted)."""
    base = c.avg if c.mode == "avg" else c.min
    return js_round(base * c.weight)


def build_leg(mutasi: MutasiExtract, angsuran: float) -> dict:
    """One applicant leg: components + THP = Σ(adjusted) − angsuran SLIK."""
    components = extract_components(mutasi)
    gross = sum(adjusted(c) for c in components)
    return {
        "components": [c.model_dump() for c in components],
        "thp": int(gross - angsuran),
    }


def build_income(
    mutasi: MutasiExtract,
    angsuran_slik: float,
    joint: bool = False,
    pasangan_mutasi: Optional[MutasiExtract] = None,
    pasangan_angsuran: float = 0,
) -> dict:
    """Nasabah leg + optional pasangan leg (joint income) + combined total."""
    nasabah = build_leg(mutasi, angsuran_slik)
    out = {"nasabah": nasabah, "total": nasabah["thp"]}
    if joint and pasangan_mutasi is not None:
        pasangan = build_leg(pasangan_mutasi, pasangan_angsuran)
        out["pasangan"] = pasangan
        out["total"] = nasabah["thp"] + pasangan["thp"]
    return out
