"""ocr_mutasi (:5004) -> UI MutasiExtract.

Verification finding (spec §3): returns per-file `transactions` + a top-level
`credits[]` (only credits carry `category`), and category totals live in
`audit.category_totals`. Renames: keterangan->remark, amount->nominal,
type DB/CR->Debit/Kredit; rebuilds count/totals/gajiNominal/ringkasan the UI
expects but the service does not forward at top level.
"""

from typing import Any, List, Optional

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_files


def normalize_mutasi(raw: dict) -> dict:
    files = raw.get("files", []) or []
    credits = raw.get("credits", []) or []
    audit = raw.get("audit", {}) or {}
    cat_totals = audit.get("category_totals", {}) or {}

    transactions: List[dict] = []
    # Classified credit rows (the income rows the dashboard cares about).
    for c in credits:
        transactions.append({
            "tanggal": c.get("tanggal", ""),
            "remark": c.get("keterangan", ""),
            "nominal": c.get("amount", 0) or 0,
            "dk": "Kredit",
            "klasifikasi": c.get("category") or "Lainnya",
        })
    # Debit rows from per-file transactions (no classification upstream).
    for f in files:
        for t in (f.get("transactions", []) or []):
            if t.get("type") == "DB":
                transactions.append({
                    "tanggal": t.get("tanggal", ""),
                    "remark": t.get("keterangan", ""),
                    "nominal": t.get("amount", 0) or 0,
                    "dk": "Debit",
                    "klasifikasi": "Lainnya",
                })

    total_kredit = sum(t["nominal"] for t in transactions if t["dk"] == "Kredit")
    total_debet = sum(t["nominal"] for t in transactions if t["dk"] == "Debit")
    ringkasan = {k: (v.get("sum") or 0) for k, v in cat_totals.items()}
    gaji_nominal = (cat_totals.get("Gaji", {}) or {}).get("min")

    no_rek: Optional[str] = None
    file_names: List[str] = []
    for f in files:
        acc = f.get("account", {}) or {}
        if no_rek is None and acc.get("no_rekening"):
            no_rek = acc.get("no_rekening")
        if f.get("filename"):
            file_names.append(f.get("filename"))

    return {
        "transactions": transactions,
        "noRekening": no_rek,
        "count": len(transactions),
        "totalKredit": total_kredit,
        "totalDebet": total_debet,
        "gajiNominal": gaji_nominal,
        "ringkasan": ringkasan,
        "fileName": file_names or None,
    }


async def fetch_mutasi(files: Any) -> dict:
    s = get_settings()
    raw = await post_files(
        "{}/api/v1/mutations/extract-batch".format(s.mutasi_url), files=files, service="mutasi"
    )
    return normalize_mutasi(raw)
