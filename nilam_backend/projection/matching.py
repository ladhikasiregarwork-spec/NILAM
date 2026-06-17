"""Slip <-> Mutasi monthly reconciliation. PORT of `engines/matching/matchSlipMutasi.ts`
(`buildMatch`). Owns the monthly-recap aggregation server-side (was the browser's job).

Builds a transaction list (Gaji/THR/Bonus credits) and a per-month recap that pairs
the statement income with each slip's Total Upah / Total Potongan. THR/bonus are
taken from the mutasi classification; the slip supplies gross/pokok/potongan.
"""

import re
from typing import List, Optional

from nilam_backend.domain.documents import MutasiExtract, SlipGajiExtract

MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

MONTH_NAMES = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3, "apr": 4, "april": 4, "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6, "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8, "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}


def _mutasi_month_key(tgl: str) -> str:
    p = tgl.split("/")  # DD MM YY
    return "{}/{}".format(p[1], p[2]) if len(p) == 3 else tgl


def _month_label(key: str) -> str:
    mm, yy = key.split("/")
    idx = int(mm) - 1
    name = MONTHS_ID[idx] if 0 <= idx < len(MONTHS_ID) else mm
    return "{} 20{}".format(name, yy)


def _slip_month_key(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    # Full date DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY (BRI slip: "25.05.2026").
    full = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if full:
        return "{}/{}".format(full.group(2).zfill(2), full.group(3)[-2:])
    named = re.search(r"([A-Za-z]+)\s+(\d{4})", s)
    if named:
        num = MONTH_NAMES.get(named.group(1).lower())
        if num:
            return "{:02d}/{}".format(num, named.group(2)[2:])
    numeric = re.search(r"(\d{1,2})[./-](\d{2,4})", s)
    if numeric:
        return "{}/{}".format(numeric.group(1).zfill(2), numeric.group(2)[-2:])
    return None


def _to_int(x: str) -> int:
    try:
        return int(x)
    except (ValueError, TypeError):
        return 0


def _key_order(k: str) -> int:
    parts = k.split("/")
    mm = _to_int(parts[0]) if len(parts) > 0 else 0
    yy = _to_int(parts[1]) if len(parts) > 1 else 0
    return yy * 100 + mm


def _txn_order(t: str) -> int:
    parts = t.split("/")
    dd = _to_int(parts[0]) if len(parts) > 0 else 0
    mm = _to_int(parts[1]) if len(parts) > 1 else 0
    yy = _to_int(parts[2]) if len(parts) > 2 else 0
    return yy * 10000 + mm * 100 + dd


def build_match(mutasi: Optional[MutasiExtract], slip: Optional[SlipGajiExtract]) -> dict:
    """Return {"txns": MatchTxn[], "recaps": MonthlyRecap[]} (mirrors buildMatch)."""
    txns: List[dict] = []
    for t in (mutasi.transactions if mutasi else []):
        if t.dk != "Kredit":
            continue
        k = t.klasifikasi
        if k in ("Gaji", "THR", "Bonus"):
            txns.append({
                "tanggal": t.tanggal,
                "gaji": t.nominal if k == "Gaji" else 0,
                "thr": t.nominal if k == "THR" else 0,
                "bonus": t.nominal if k == "Bonus" else 0,
                "remark": t.remark,
            })

    recap_map: dict = {}

    def ensure(key: str) -> dict:
        r = recap_map.get(key)
        if r is None:
            r = {"key": key, "bulan": _month_label(key),
                 "gajiMutasi": 0, "thrMutasi": 0, "bonusMutasi": 0}
            recap_map[key] = r
        return r

    for t in txns:
        r = ensure(_mutasi_month_key(t["tanggal"]))
        r["gajiMutasi"] += t["gaji"]
        r["thrMutasi"] += t["thr"]
        r["bonusMutasi"] += t["bonus"]

    for rec in (slip.records if slip else []):
        key = _slip_month_key(rec.tanggalPembayaran)
        if not key:
            continue
        r = ensure(key)
        if rec.thp is not None:
            r["gajiSlip"] = r.get("gajiSlip", 0) + rec.thp  # THP <-> gaji mutasi
        if rec.thr is not None:
            r["thrSlip"] = r.get("thrSlip", 0) + rec.thr
        if rec.bonus is not None:
            r["bonusSlip"] = r.get("bonusSlip", 0) + rec.bonus
        if rec.gajiPokok is not None:
            r["gajiPokokSlip"] = r.get("gajiPokokSlip", 0) + rec.gajiPokok
        if rec.tunjangan is not None:
            r["tunjanganSlip"] = r.get("tunjanganSlip", 0) + rec.tunjangan
        if rec.totalUpah is not None:
            r["incomeSlip"] = r.get("incomeSlip", 0) + rec.totalUpah
        if rec.totalPotongan is not None:
            r["potonganSlip"] = r.get("potonganSlip", 0) + rec.totalPotongan
            net = rec.totalPotongan - (rec.potonganBonus or 0) - (rec.potonganThr or 0) - (rec.potonganCuti or 0)
            r["potonganNet"] = r.get("potonganNet", 0) + net
        if rec.tanggalPembayaran:
            r["tglBayarSlip"] = rec.tanggalPembayaran

    txns.sort(key=lambda a: _txn_order(a["tanggal"]))
    recaps = sorted(recap_map.values(), key=lambda a: _key_order(a["key"]))
    return {"txns": txns, "recaps": recaps}
