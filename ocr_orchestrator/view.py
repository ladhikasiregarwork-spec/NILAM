# ocr_orchestrator/view.py
"""Pure, total projector: domain ApplicationResult (+ echoed inputs + raw
upstream payloads) -> the UI-shaped ApplicationView. No I/O; missing inputs
project to null/empty, never raises. The only place the dashboard shape lives.

See docs/superpowers/specs/2026-06-12-orchestrator-application-view-design.md.
"""
from __future__ import annotations

from typing import Any, Optional

from .models import (
    AgunanInput, AgunanView, CollateralInput, EmploymentView, FmvResult,
    IdentityView, KtpView,
)


def _search(node: Any, keys: tuple[str, ...]) -> Optional[str]:
    """First non-empty string under any of ``keys``, searched recursively
    (mirrors identity._search_key — the SK/KK payload shapes vary)."""
    if isinstance(node, dict):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in node.values():
            found = _search(v, keys)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _search(item, keys)
            if found:
                return found
    return None


def _f(value: Any) -> Optional[float]:
    """Coerce to float; None/unparseable -> None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def project_identity(name: Optional[str]) -> IdentityView:
    """User Information section. Only ktp.nama is filled in v1 (D2 stub)."""
    return IdentityView(ktp=KtpView(nama=name))


def project_agunan(
    collateral: Optional[CollateralInput],
    agunan: Optional[AgunanInput],
    fmv: Optional[FmvResult],
) -> AgunanView:
    """NPW & Informasi Agunan: echo the inputs, set npw = fmv.fair_value."""
    return AgunanView(
        harga_rumah=agunan.harga_rumah if agunan else None,
        luas_tanah=collateral.luas_tanah if collateral else None,
        luas_bangunan=collateral.luas_bangunan if collateral else None,
        provinsi=agunan.provinsi if agunan else None,
        kota_kab=agunan.kota_kab if agunan else None,
        kecamatan=agunan.kecamatan if agunan else None,
        kelurahan=collateral.kelurahan if collateral else None,
        kode_pos=collateral.kode_pos if collateral else None,
        npw=fmv.fair_value if fmv else None,
        fmv=fmv,
    )


def project_employment(sk_response: Any) -> Optional[EmploymentView]:
    """Project the Company Employment Certificate section from ocr_sk output."""
    if not sk_response:
        return None
    perusahaan = _search(sk_response, ("institution_name", "nama_institusi"))
    jabatan = _search(sk_response, ("position", "jabatan"))
    status = _search(sk_response, ("employment_status", "status_karyawan"))
    masa_kerja = _search(sk_response, ("tenure", "masa_kerja"))
    start_date = _search(sk_response, ("start_date", "tanggal_mulai_kerja"))
    if not any((perusahaan, jabatan, status, masa_kerja, start_date)):
        return None
    return EmploymentView(
        perusahaan=perusahaan, jabatan=jabatan, status=status,
        masa_kerja=masa_kerja, start_date=start_date,
    )
