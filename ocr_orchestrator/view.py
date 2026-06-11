# ocr_orchestrator/view.py
"""Pure, total projector: domain ApplicationResult (+ echoed inputs + raw
upstream payloads) -> the UI-shaped ApplicationView. No I/O; missing inputs
project to null/empty, never raises. The only place the dashboard shape lives.

See docs/superpowers/specs/2026-06-12-orchestrator-application-view-design.md.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from .models import (
    AgunanInput, AgunanView, BankStatementView, CollateralInput, CreditView,
    DecisionResult, EmploymentView, FmvResult, IdentityView, IncomeBreakdown,
    InstallmentView, KlasifikasiPemasukan, KtpView, MatchingView, RekapRow,
    SlipView,
)
from .slip_dates import credit_month, slip_month


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


def project_installment(
    income: Optional[IncomeBreakdown],
    decision: Optional[DecisionResult],
) -> Optional[InstallmentView]:
    """Kemampuan Bayar from income + decision. SLIK deduction is 0 for now."""
    if income is None:
        return None
    slik = decision.existing_installment if decision else 0.0
    qi = income.monthly_qualifying_income
    kemampuan = (qi - slik) if qi is not None else None
    return InstallmentView(
        gaji_bulanan=income.avg_monthly_gaji_insentif,
        thr_bulanan=income.monthly_thr,
        bonus_bulanan=income.bonus_monthly,
        bonus_total=income.bonus_total,
        bonus_accept_pct=income.bonus_accept_pct,
        monthly_qualifying_income=qi,
        slik_deduction=slik,
        kemampuan_bayar=kemampuan,
        angsuran_kpr=decision.monthly_installment if decision else None,
        verdict=decision.recommendation if decision else None,
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


_INCOME_CATEGORIES = ("Gaji", "THR", "Bonus", "Insentif")


def project_credit(c: dict[str, Any]) -> CreditView:
    return CreditView(
        tanggal=c.get("tanggal"), amount=_f(c.get("amount")),
        category=c.get("category"), keterangan=c.get("keterangan"),
        month=credit_month(c.get("tanggal")),
    )


def project_transaksi_pemasukan(credits: list[dict[str, Any]]) -> list[CreditView]:
    return [project_credit(c) for c in credits
            if c.get("category") in _INCOME_CATEGORIES]


def project_salary_slips(slip_docs: list[dict[str, Any]]) -> list[SlipView]:
    rows: list[SlipView] = []
    for d in slip_docs:
        thp = _f(d.get("total_paid"))
        potongan = _f(d.get("deduction"))
        rows.append(SlipView(
            tgl_pembayaran=d.get("period") or slip_month(d),
            total_upah=(thp or 0.0) + (potongan or 0.0),
            potongan=potongan,
            thp=thp,
            thr=_f(d.get("thr")),
            bonus=_f(d.get("incentive")),
        ))
    return rows


def project_rekap(
    credits: list[dict[str, Any]],
    slip_docs: list[dict[str, Any]],
    matches: list,
) -> list[RekapRow]:
    """Per-month slip-vs-mutasi split (spec §6)."""
    mut: dict[str, dict[str, float]] = defaultdict(
        lambda: {"gaji": 0.0, "thr": 0.0, "bonus": 0.0})
    for c in credits:
        cat = c.get("category")
        if cat not in _INCOME_CATEGORIES:
            continue
        month = credit_month(c.get("tanggal"))
        if not month:
            continue
        amount = _f(c.get("amount")) or 0.0
        if cat == "Gaji":
            mut[month]["gaji"] += amount
        elif cat == "THR":
            mut[month]["thr"] += amount
        else:                                  # Bonus or Insentif
            mut[month]["bonus"] += amount

    matched_home: dict[str, str] = {}
    for pair in matches:
        sf = pair.slip.source_file
        cm = pair.credit.month
        if sf and cm:
            matched_home[sf] = cm

    slip: dict[str, dict[str, float]] = defaultdict(
        lambda: {"gaji": 0.0, "thr": 0.0, "bonus": 0.0, "income": 0.0})
    for d in slip_docs:
        sf = d.get("source_file")
        home = matched_home.get(sf) or slip_month(d)
        if not home:
            continue
        thp = _f(d.get("total_paid")) or 0.0
        potongan = _f(d.get("deduction")) or 0.0
        s = slip[home]
        s["gaji"] += thp
        s["thr"] += _f(d.get("thr")) or 0.0
        s["bonus"] += _f(d.get("incentive")) or 0.0
        s["income"] += thp + potongan

    rows: list[RekapRow] = []
    for month in sorted(set(mut) | set(slip)):
        m = mut.get(month)
        s = slip.get(month)
        gaji_slip = s["gaji"] if s else None
        thr_slip = s["thr"] if s else None
        income_slip = s["income"] if s else None
        potongan = None
        if income_slip is not None:
            # potongan = deductions excluding THR (income_slip - gaji_slip - thr_slip)
            potongan = income_slip - (gaji_slip or 0.0) - (thr_slip or 0.0)
        rows.append(RekapRow(
            bulan=month,
            gaji_slip=gaji_slip, gaji_mutasi=m["gaji"] if m else None,
            thr_slip=thr_slip, thr_mutasi=m["thr"] if m else None,
            bonus_slip=s["bonus"] if s else None, bonus_mutasi=m["bonus"] if m else None,
            income_slip=income_slip, potongan=potongan,
        ))
    return rows


def project_bank_statement(credits: list[dict[str, Any]]) -> BankStatementView:
    """Bank Statement: classified credits + totals (debit ledger deferred, D5)."""
    kl = KlasifikasiPemasukan()
    total_kredit = 0.0
    views: list[CreditView] = []
    for c in credits:
        amount = _f(c.get("amount")) or 0.0
        total_kredit += amount
        cat = c.get("category")
        if cat == "Gaji":
            kl.gaji += amount
        elif cat == "THR":
            kl.thr += amount
        elif cat == "Bonus":
            kl.bonus += amount
        views.append(project_credit(c))
    return BankStatementView(
        klasifikasi=kl, total_kredit=total_kredit, total_debet=0.0,
        n_transaksi=len(credits), credits=views,
    )
