"""ocr_slip (:5003) -> UI SlipRecord[] (SlipGajiExtract).

Verification finding (spec §3): the slip service renames fields and has a real
data gap — no separate thr/bonus (left unset here) — and exposes per-document
rows under `summary.dokumen[]` with Indonesian keys. Mapping:
  tanggal_periode->tanggalPembayaran, gaji_pokok->gajiPokok, tunjangan->tunjangan,
  potongan->totalPotongan. Total Upah (gross) = gaji_pokok + tunjangan (the earning
  lines); take-home thp = totalUpah - potongan. Falls back to total_dibayar+potongan
  when the earning lines are absent.
"""

from typing import Any

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_files


def normalize_slip(raw: dict) -> dict:
    summary = raw.get("summary", {}) or {}
    dokumen = summary.get("dokumen", []) or []
    records = []
    for d in dokumen:
        gaji_pokok = d.get("gaji_pokok") or 0
        tunjangan = d.get("tunjangan") or 0
        potongan = d.get("potongan") or 0
        total_dibayar = d.get("total_dibayar")
        total_upah = (gaji_pokok + tunjangan) if (gaji_pokok or tunjangan) else ((total_dibayar or 0) + potongan)
        records.append({
            "tanggalPembayaran": d.get("tanggal_periode"),
            "totalUpah": total_upah,
            "totalPotongan": potongan,
            "thp": total_upah - potongan,
            "gajiPokok": gaji_pokok,
            "tunjangan": tunjangan,
            "fileName": d.get("sumber_file"),
        })
    return {"records": records}


async def fetch_slip(files: Any, password: Any = None) -> dict:
    s = get_settings()
    data = {"password": password} if password else None
    raw = await post_files("{}/parse".format(s.slip_url), files=files, data=data, service="slip")
    return normalize_slip(raw)
