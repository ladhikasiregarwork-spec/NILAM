"""ocr_sk (:5002) -> UI SkPerusahaanExtract.

Verification finding (spec §3): ocr_sk matches the UI shape up to snake->camel
renames. Reads the first `summary.dokumen[]` row. When no document parsed and the
PDF was not password-locked, the document is treated as not-an-SK (`rejected`).
"""

from typing import Any

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_files


def normalize_sk(raw: dict) -> dict:
    summary = raw.get("summary", {}) or {}
    dokumen = summary.get("dokumen", []) or []
    needs_pw = bool(raw.get("needs_password"))
    if not dokumen:
        return {"needsPassword": needs_pw, "rejected": not needs_pw}
    d = dokumen[0]
    return {
        "perusahaan": d.get("nama_institusi"),
        "jabatan": d.get("jabatan"),
        "statusKepegawaian": d.get("status_karyawan"),
        "masaKerja": d.get("masa_kerja"),
        "tanggalMulai": d.get("tanggal_mulai_kerja"),
        "tanggalBerakhir": d.get("tanggal_akhir_kerja"),
        "namaPekerja": d.get("nama_pekerja"),
        "nik": d.get("nik"),
        "nomorSurat": d.get("nomor_surat"),
        "tanggalSurat": d.get("tanggal_surat"),
        "fileName": d.get("sumber_file"),
        "needsPassword": needs_pw,
    }


async def fetch_sk(files: Any, password: Any = None) -> dict:
    s = get_settings()
    data = {"password": password} if password else None
    raw = await post_files("{}/parse".format(s.sk_url), files=files, data=data, service="sk")
    return normalize_sk(raw)
