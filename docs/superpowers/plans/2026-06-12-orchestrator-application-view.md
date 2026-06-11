# Orchestrator UI-shaped `ApplicationView` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ocr_orchestrator` to accept the assessment dashboard's user inputs and serve one UI-shaped `ApplicationView` (per `docs/superpowers/specs/2026-06-12-orchestrator-application-view-design.md`).

**Architecture:** The domain pipeline (classify → extract → acquire → aggregate → fmv → decide) is unchanged. A new **pure, total** projector `view.py` turns the domain `ApplicationResult` (+ echoed inputs + raw upstream payloads) into `ApplicationView`. `api.py` gains request fields and derives `loan_amount = harga_rumah − dp`; the `assemble` stage of `pipeline.py` calls the projector and stores the view.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest (unittest-style `TestCase`, matching existing tests).

**Environment notes:**
- Run all commands **from the repo root** with the shared venv: `.venv\Scripts\python` (Windows).
- This is a OneDrive checkout — commit with `git -c core.logAllRefUpdates=false commit …` (plain commit fails on reflog append).
- The projector is **pure** (no I/O) and **total** (missing inputs → `null`/empty, never raises).

---

## File structure

- **Create** `ocr_orchestrator/view.py` — the projector: helpers + one `project_*` function per section + `build_application_view`.
- **Create** `ocr_orchestrator/tests/test_view.py` — unit tests per projection + the assembler.
- **Modify** `ocr_orchestrator/models.py` — add the view models (reuse `DocumentResult`/`FmvResult`/`IncomeBreakdown`/`DecisionResult`/`VerificationInfo`/`OrchestratorAudit` as nested sub-objects).
- **Modify** `ocr_orchestrator/api.py` — new Form fields, `loan_amount = harga_rumah − dp`, build `AgunanInput`, thread it through `run_job`; `JobStatusResponse.result` → `ApplicationView`.
- **Modify** `ocr_orchestrator/pipeline.py` — at `assemble`, build and store the `ApplicationView`; `run_job`/`_execute` accept `agunan`.
- **Modify** `ocr_orchestrator/tests/test_pipeline.py`, `tests/test_api.py` — repoint result-shape assertions to `ApplicationView`.

Each task adds the model(s) it needs to `models.py` and the function(s) to `view.py`, with tests, so tasks are self-contained.

---

### Task 1: `view.py` skeleton + helpers + `EmploymentView` projection

**Files:**
- Create: `ocr_orchestrator/view.py`
- Modify: `ocr_orchestrator/models.py`
- Test: `ocr_orchestrator/tests/test_view.py`

The SK payload shape varies and uses both English (`institution_name`, `position`, `employment_status`, `start_date`, `tenure`) and Indonesian (`nama_institusi`, `jabatan`, `status_karyawan`, `tanggal_mulai_kerja`, `masa_kerja`) keys, possibly nested under `documents`/`dokumen`. Mirror `identity.py`'s recursive search.

- [ ] **Step 1: Write the failing test**

```python
# ocr_orchestrator/tests/test_view.py
import unittest

from ocr_orchestrator import view
from ocr_orchestrator.models import EmploymentView


class TestProjectEmployment(unittest.TestCase):
    def test_none_response_returns_none(self):
        self.assertIsNone(view.project_employment(None))
        self.assertIsNone(view.project_employment({}))

    def test_english_keys(self):
        sk = {
            "institution_name": "PT. BANK RAKYAT INDONESIA",
            "position": "Senior Supervisor Produksi",
            "employment_status": "Karyawan Tetap",
            "tenure": "5 tahun 3 bulan",
            "start_date": "01 Oktober 2021",
        }
        emp = view.project_employment(sk)
        self.assertEqual(emp.perusahaan, "PT. BANK RAKYAT INDONESIA")
        self.assertEqual(emp.jabatan, "Senior Supervisor Produksi")
        self.assertEqual(emp.status, "Karyawan Tetap")
        self.assertEqual(emp.masa_kerja, "5 tahun 3 bulan")
        self.assertEqual(emp.start_date, "01 Oktober 2021")

    def test_indonesian_keys_nested_under_documents(self):
        sk = {"documents": [{
            "nama_institusi": "PT. ABC",
            "jabatan": "Staff",
            "status_karyawan": "Kontrak",
            "masa_kerja": "1 tahun",
            "tanggal_mulai_kerja": "2025-01-01",
        }]}
        emp = view.project_employment(sk)
        self.assertEqual(emp.perusahaan, "PT. ABC")
        self.assertEqual(emp.jabatan, "Staff")
        self.assertEqual(emp.status, "Kontrak")

    def test_no_recognizable_fields_returns_none(self):
        self.assertIsNone(view.project_employment({"unrelated": "value"}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.view'` (and `EmploymentView` import error).

- [ ] **Step 3: Add `EmploymentView` to `models.py`**

Add after `ApplicantInfo` (around line 36):

```python
class EmploymentView(BaseModel):
    """Company Employment Certificate section, projected from the ocr_sk payload."""
    perusahaan: Optional[str] = None
    jabatan: Optional[str] = None
    status: Optional[str] = None
    masa_kerja: Optional[str] = None
    start_date: Optional[str] = None
```

- [ ] **Step 4: Create `view.py` with helpers + `project_employment`**

```python
# ocr_orchestrator/view.py
"""Pure, total projector: domain ApplicationResult (+ echoed inputs + raw
upstream payloads) -> the UI-shaped ApplicationView. No I/O; missing inputs
project to null/empty, never raises. The only place the dashboard shape lives.

See docs/superpowers/specs/2026-06-12-orchestrator-application-view-design.md.
"""
from __future__ import annotations

from typing import Any, Optional

from .models import EmploymentView


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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/view.py ocr_orchestrator/models.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): view.py projector + EmploymentView projection"
```

---

### Task 2: `IdentityView` projection (KTP name real; KK stub)

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from ocr_orchestrator.models import IdentityView  # add to imports


class TestProjectIdentity(unittest.TestCase):
    def test_name_populated_rest_null(self):
        idv = view.project_identity("MUHAMMAD ARIE")
        self.assertEqual(idv.ktp.nama, "MUHAMMAD ARIE")
        self.assertIsNone(idv.ktp.nik)
        self.assertIsNone(idv.ktp.gender)
        self.assertIsNone(idv.kk.no_kk)
        self.assertEqual(idv.kk.anggota, [])

    def test_none_name(self):
        idv = view.project_identity(None)
        self.assertIsNone(idv.ktp.nama)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestProjectIdentity -v`
Expected: FAIL — `ImportError: cannot import name 'IdentityView'`.

- [ ] **Step 3: Add identity models to `models.py`**

```python
class KtpView(BaseModel):
    nama: Optional[str] = None
    nik: Optional[str] = None
    gender: Optional[str] = None
    tgl_lahir: Optional[str] = None
    age: Optional[int] = None


class AnggotaKeluarga(BaseModel):
    nama: Optional[str] = None
    nik: Optional[str] = None


class KkView(BaseModel):
    no_kk: Optional[str] = None
    kepala_keluarga: Optional[str] = None
    anggota: list[AnggotaKeluarga] = Field(default_factory=list)


class IdentityView(BaseModel):
    """User Information section. v1: ktp.nama is real; everything else is a
    stub (null) until a KTP/KK extractor lands."""
    ktp: KtpView = Field(default_factory=KtpView)
    kk: KkView = Field(default_factory=KkView)
```

- [ ] **Step 4: Add `project_identity` to `view.py`**

```python
from .models import EmploymentView, IdentityView, KtpView  # update import line


def project_identity(name: Optional[str]) -> IdentityView:
    """User Information section. Only ktp.nama is filled in v1 (D2 stub)."""
    return IdentityView(ktp=KtpView(nama=name))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): IdentityView projection (KTP name real, KK stub)"
```

---

### Task 3: `AgunanView` + `AgunanInput` projection (echo + NPW)

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from ocr_orchestrator.models import AgunanInput, AgunanView, CollateralInput, FmvResult


class TestProjectAgunan(unittest.TestCase):
    def _fmv(self):
        return FmvResult(land_value=3.0, building_value=2.0, fair_value=5.0,
                         location_matched=True, backend="linear")

    def test_full(self):
        col = CollateralInput(luas_tanah=96.0, luas_bangunan=45.0,
                              kode_pos="16969", kelurahan="Bojong Kulur")
        ag = AgunanInput(provinsi="Jawa Barat", kota_kab="Bogor",
                         kecamatan="Bojong Kulur", harga_rumah=610_000_000.0)
        out = view.project_agunan(col, ag, self._fmv())
        self.assertEqual(out.harga_rumah, 610_000_000.0)
        self.assertEqual(out.luas_tanah, 96.0)
        self.assertEqual(out.kelurahan, "Bojong Kulur")
        self.assertEqual(out.provinsi, "Jawa Barat")
        self.assertEqual(out.npw, 5.0)               # = fmv.fair_value
        self.assertEqual(out.fmv.fair_value, 5.0)

    def test_no_fmv_npw_null(self):
        out = view.project_agunan(None, None, None)
        self.assertIsNone(out.npw)
        self.assertIsNone(out.harga_rumah)
        self.assertIsNone(out.luas_tanah)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestProjectAgunan -v`
Expected: FAIL — `ImportError: cannot import name 'AgunanInput'`.

- [ ] **Step 3: Add agunan models to `models.py`**

```python
class AgunanInput(BaseModel):
    """Agunan display fields the orchestrator echoes (not FMV inputs)."""
    provinsi: Optional[str] = None
    kota_kab: Optional[str] = None
    kecamatan: Optional[str] = None
    harga_rumah: Optional[float] = None


class AgunanView(BaseModel):
    """NPW & Informasi Agunan section. npw == fmv.fair_value."""
    harga_rumah: Optional[float] = None
    luas_tanah: Optional[float] = None
    luas_bangunan: Optional[float] = None
    provinsi: Optional[str] = None
    kota_kab: Optional[str] = None
    kecamatan: Optional[str] = None
    kelurahan: Optional[str] = None
    kode_pos: Optional[str] = None
    npw: Optional[float] = None
    fmv: Optional[FmvResult] = None
```

(`FmvResult` is already defined above in `models.py`.)

- [ ] **Step 4: Add `project_agunan` to `view.py`**

```python
from .models import (  # update import line
    AgunanInput, AgunanView, CollateralInput, EmploymentView, FmvResult,
    IdentityView, KtpView,
)


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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): AgunanView projection (echo inputs + npw=fmv.fair_value)"
```

---

### Task 4: `InstallmentView` projection (income + decision)

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

`kemampuan_bayar = monthly_qualifying_income − slik_deduction`; `slik_deduction = decision.existing_installment` (0 now, D1/D5). `verdict = decision.recommendation`.

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from ocr_orchestrator.models import (  # extend import
    DecisionResult, InstallmentView, IncomeBreakdown,
)


def _income(**kw):
    base = dict(n_statement_months=3, avg_monthly_gaji_insentif=14_598_876.0,
                monthly_thr=2_753_552.0, bonus_total=54_933_362.0,
                bonus_accept_pct=0.5, bonus_monthly=2_288_890.0,
                monthly_qualifying_income=19_641_318.0, basis="bank_verified",
                verified_month_count=3)
    base.update(kw)
    return IncomeBreakdown(**base)


class TestProjectInstallment(unittest.TestCase):
    def test_from_income_and_decision(self):
        dec = DecisionResult(recommendation="eligible", monthly_installment=4_532_136.0,
                             monthly_income=19_641_318.0, existing_installment=0.0)
        out = view.project_installment(_income(), dec)
        self.assertEqual(out.gaji_bulanan, 14_598_876.0)
        self.assertEqual(out.thr_bulanan, 2_753_552.0)
        self.assertEqual(out.bonus_bulanan, 2_288_890.0)
        self.assertEqual(out.slik_deduction, 0.0)
        self.assertEqual(out.kemampuan_bayar, 19_641_318.0)   # qi - slik
        self.assertEqual(out.angsuran_kpr, 4_532_136.0)
        self.assertEqual(out.verdict, "eligible")

    def test_none_income_returns_none(self):
        self.assertIsNone(view.project_installment(None, None))

    def test_no_decision_uses_zero_slik(self):
        out = view.project_installment(_income(monthly_qualifying_income=None,
                                               basis="none"), None)
        self.assertEqual(out.slik_deduction, 0.0)
        self.assertIsNone(out.kemampuan_bayar)
        self.assertIsNone(out.verdict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestProjectInstallment -v`
Expected: FAIL — `ImportError: cannot import name 'InstallmentView'`.

- [ ] **Step 3: Add `InstallmentView` to `models.py`**

```python
class InstallmentView(BaseModel):
    """Calculate Installment / Kemampuan Bayar section (D1: served computed)."""
    gaji_bulanan: Optional[float] = None
    thr_bulanan: Optional[float] = None
    bonus_bulanan: Optional[float] = None
    bonus_total: Optional[float] = None
    bonus_accept_pct: Optional[float] = None
    monthly_qualifying_income: Optional[float] = None
    slik_deduction: float = 0.0
    kemampuan_bayar: Optional[float] = None
    angsuran_kpr: Optional[float] = None
    verdict: Optional[str] = None
```

- [ ] **Step 4: Add `project_installment` to `view.py`**

```python
from .models import (  # extend import
    AgunanInput, AgunanView, CollateralInput, DecisionResult, EmploymentView,
    FmvResult, IdentityView, IncomeBreakdown, InstallmentView, KtpView,
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): InstallmentView projection (income+decision)"
```

---

### Task 5: Matching section — `transaksi_pemasukan`, `salary_slip`, `rekap_per_bulan`

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

Reuse `slip_dates.slip_month`/`credit_month` for month homing (same as `monthly.py`). Inferred column semantics from the spec (§6): `gaji_slip = total_paid` (THP), `income_slip = total_paid + deduction` (Total Upah), `potongan = income_slip − gaji_slip − thr_slip`. These reconcile with the screenshot; confirm against `ocr_slip` output during execution and adjust if the slip carries explicit `thr`/`bonus` fields.

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from types import SimpleNamespace
from ocr_orchestrator.models import CreditView, MatchingView, RekapRow, SlipView


def _credit(category, amount, tanggal):
    return {"source_file": "mut.pdf", "tanggal": tanggal, "amount": amount,
            "category": category, "keterangan": category.upper()}


def _slip(source_file, total_paid, deduction=0.0, incentive=0.0, thr=None, period=None):
    return {"source_file": source_file, "total_paid": total_paid,
            "deduction": deduction, "incentive": incentive, "thr": thr,
            "period": period}


def _matchview(slip_source_file, credit_month):
    return SimpleNamespace(slip=SimpleNamespace(source_file=slip_source_file),
                           credit=SimpleNamespace(month=credit_month))


class TestProjectMatching(unittest.TestCase):
    def test_transaksi_pemasukan_keeps_income_categories(self):
        credits = [_credit("Gaji", 100, "2026-03-25"),
                   _credit("Lainnya", 9, "2026-03-02")]
        out = view.project_transaksi_pemasukan(credits)
        self.assertEqual([c.category for c in out], ["Gaji"])
        self.assertEqual(out[0].month, "2026-03")

    def test_salary_slip_table(self):
        slips = [_slip("s.pdf", total_paid=14_598_876.0, deduction=47_662_544.0,
                       thr=33_042_624.0, period="2026-03")]
        out = view.project_salary_slips(slips)
        s = out[0]
        self.assertEqual(s.thp, 14_598_876.0)
        self.assertEqual(s.potongan, 47_662_544.0)
        self.assertEqual(s.total_upah, 62_261_420.0)   # thp + potongan
        self.assertEqual(s.thr, 33_042_624.0)

    def test_rekap_slip_plus_mutasi_split(self):
        credits = [_credit("Gaji", 14_598_876.0, "2026-03-25"),
                   _credit("THR", 33_042_624.0, "2026-03-05"),
                   _credit("Bonus", 54_933_362.0, "2026-03-17")]
        slips = [_slip("s.pdf", total_paid=14_598_876.0, deduction=47_662_544.0,
                       incentive=0.0, thr=33_042_624.0, period="2026-03")]
        matches = [_matchview("s.pdf", "2026-03")]
        rows = view.project_rekap(credits, slips, matches)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.bulan, "2026-03")
        self.assertEqual(r.gaji_mutasi, 14_598_876.0)
        self.assertEqual(r.thr_mutasi, 33_042_624.0)
        self.assertEqual(r.bonus_mutasi, 54_933_362.0)
        self.assertEqual(r.gaji_slip, 14_598_876.0)            # THP
        self.assertEqual(r.thr_slip, 33_042_624.0)
        self.assertEqual(r.income_slip, 62_261_420.0)          # THP + deduction
        self.assertEqual(r.potongan, 14_619_920.0)             # income - gaji - thr
        self.assertEqual(r.status, "non-edited")

    def test_rekap_unmatched_slip_still_creates_row(self):
        slips = [_slip("s.pdf", total_paid=1_000.0, deduction=200.0, period="2026-05")]
        rows = view.project_rekap([], slips, [])
        self.assertEqual([r.bulan for r in rows], ["2026-05"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestProjectMatching -v`
Expected: FAIL — `ImportError: cannot import name 'CreditView'`.

- [ ] **Step 3: Add matching models to `models.py`**

```python
class CreditView(BaseModel):
    tanggal: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    keterangan: Optional[str] = None
    month: Optional[str] = None


class SlipView(BaseModel):
    tgl_pembayaran: Optional[str] = None
    total_upah: Optional[float] = None
    potongan: Optional[float] = None
    thp: Optional[float] = None
    thr: Optional[float] = None
    bonus: Optional[float] = None


class RekapRow(BaseModel):
    bulan: str
    gaji_slip: Optional[float] = None
    gaji_mutasi: Optional[float] = None
    thr_slip: Optional[float] = None
    thr_mutasi: Optional[float] = None
    bonus_slip: Optional[float] = None
    bonus_mutasi: Optional[float] = None
    income_slip: Optional[float] = None
    potongan: Optional[float] = None
    status: str = "non-edited"


class MatchingView(BaseModel):
    transaksi_pemasukan: list[CreditView] = Field(default_factory=list)
    rekap_per_bulan: list[RekapRow] = Field(default_factory=list)
    salary_slip: list[SlipView] = Field(default_factory=list)
```

- [ ] **Step 4: Add the three projections to `view.py`**

Extend the import: add `CreditView, MatchingView, RekapRow, SlipView` to the `from .models import (...)` block, and add `from .slip_dates import credit_month, slip_month` near the top.

```python
from collections import defaultdict

from .slip_dates import credit_month, slip_month

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
        thp = _f(d.get("total_paid")) or 0.0
        potongan = _f(d.get("deduction")) or 0.0
        rows.append(SlipView(
            tgl_pembayaran=d.get("period") or slip_month(d),
            total_upah=thp + potongan,
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
            potongan = income_slip - (gaji_slip or 0.0) - (thr_slip or 0.0)
        rows.append(RekapRow(
            bulan=month,
            gaji_slip=gaji_slip, gaji_mutasi=m["gaji"] if m else None,
            thr_slip=thr_slip, thr_mutasi=m["thr"] if m else None,
            bonus_slip=s["bonus"] if s else None, bonus_mutasi=m["bonus"] if m else None,
            income_slip=income_slip, potongan=potongan,
        ))
    return rows
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): matching projections (transaksi/salary_slip/rekap split)"
```

---

### Task 6: `BankStatementView` projection (credits + totals)

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

D5: classified credits + totals only (no debit ledger yet). `total_debet` stays 0 until `ocr_mutasi` exposes debits.

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from ocr_orchestrator.models import BankStatementView


class TestProjectBankStatement(unittest.TestCase):
    def test_totals_and_klasifikasi(self):
        credits = [_credit("Gaji", 14_598_876.0, "2026-03-25"),
                   _credit("THR", 33_042_624.0, "2026-03-05"),
                   _credit("Bonus", 54_933_362.0, "2026-03-17"),
                   _credit("Insentif", 1_000.0, "2026-03-17")]
        bs = view.project_bank_statement(credits)
        self.assertEqual(bs.klasifikasi.gaji, 14_598_876.0)
        self.assertEqual(bs.klasifikasi.thr, 33_042_624.0)
        self.assertEqual(bs.klasifikasi.bonus, 54_933_362.0)
        self.assertEqual(bs.n_transaksi, 4)
        self.assertEqual(bs.total_kredit, 14_598_876.0 + 33_042_624.0 + 54_933_362.0 + 1_000.0)
        self.assertEqual(bs.total_debet, 0.0)          # debits deferred (D5)
        self.assertEqual(len(bs.credits), 4)

    def test_empty(self):
        bs = view.project_bank_statement([])
        self.assertEqual(bs.n_transaksi, 0)
        self.assertEqual(bs.total_kredit, 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestProjectBankStatement -v`
Expected: FAIL — `ImportError: cannot import name 'BankStatementView'`.

- [ ] **Step 3: Add bank-statement models to `models.py`**

```python
class KlasifikasiPemasukan(BaseModel):
    gaji: float = 0.0
    thr: float = 0.0
    bonus: float = 0.0
    tunjangan_cuti: float = 0.0


class BankStatementView(BaseModel):
    klasifikasi: KlasifikasiPemasukan = Field(default_factory=KlasifikasiPemasukan)
    total_kredit: float = 0.0
    total_debet: float = 0.0
    n_transaksi: int = 0
    credits: list[CreditView] = Field(default_factory=list)
```

- [ ] **Step 4: Add `project_bank_statement` to `view.py`**

Add `BankStatementView, KlasifikasiPemasukan` to the models import.

```python
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
        elif cat in ("Bonus", "Insentif"):
            kl.bonus += amount
        views.append(project_credit(c))
    return BankStatementView(
        klasifikasi=kl, total_kredit=total_kredit, total_debet=0.0,
        n_transaksi=len(credits), credits=views,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): BankStatementView projection (credits + totals)"
```

---

### Task 7: `ApplicationView` model + `build_application_view` assembler

**Files:**
- Modify: `ocr_orchestrator/models.py`, `ocr_orchestrator/view.py`
- Test: `ocr_orchestrator/tests/test_view.py`

- [ ] **Step 1: Write the failing test**

```python
# append to test_view.py
from ocr_orchestrator.models import (
    ApplicantInfo, ApplicationResult, ApplicationView, OrchestratorAudit,
    VerificationInfo,
)


class TestBuildApplicationView(unittest.TestCase):
    def _result(self, **kw):
        base = dict(
            documents=[], applicant=ApplicantInfo(name="ARIE", name_source="slip"),
            income=_income(), verification=VerificationInfo(matched_count=1),
            collateral=CollateralInput(luas_tanah=96.0, luas_bangunan=45.0,
                                       kode_pos="16969", kelurahan="Bojong Kulur"),
            loan=None,
            fmv=FmvResult(land_value=3.0, building_value=2.0, fair_value=610_000_000.0,
                          location_matched=True, backend="linear"),
            decision=DecisionResult(recommendation="eligible",
                                    monthly_installment=4_532_136.0),
            audit=OrchestratorAudit(),
        )
        base.update(kw)
        return ApplicationResult(**base)

    def test_assembles_all_sections(self):
        av = view.build_application_view(
            self._result(),
            agunan_input=AgunanInput(provinsi="Jawa Barat", harga_rumah=610_000_000.0),
            sk_response={"institution_name": "PT. BRI", "position": "Supervisor"},
            slip_docs=[_slip("s.pdf", total_paid=14_598_876.0, deduction=47_662_544.0,
                             thr=33_042_624.0, period="2026-03")],
            credits=[_credit("Gaji", 14_598_876.0, "2026-03-25")],
            matches=[_matchview("s.pdf", "2026-03")],
        )
        self.assertIsInstance(av, ApplicationView)
        self.assertEqual(av.identity.ktp.nama, "ARIE")
        self.assertEqual(av.employment.perusahaan, "PT. BRI")
        self.assertEqual(av.agunan.npw, 610_000_000.0)
        self.assertEqual(av.agunan.harga_rumah, 610_000_000.0)
        self.assertEqual(av.installment.verdict, "eligible")
        self.assertEqual(len(av.matching.rekap_per_bulan), 1)
        self.assertEqual(av.bank_statement.n_transaksi, 1)
        self.assertEqual(av.decision.recommendation, "eligible")
        self.assertEqual(av.verification.matched_count, 1)

    def test_total_on_empty_inputs(self):
        empty = ApplicationResult(
            documents=[], applicant=ApplicantInfo(), income=None,
            verification=VerificationInfo(), audit=OrchestratorAudit())
        av = view.build_application_view(empty, agunan_input=None, sk_response=None,
                                         slip_docs=[], credits=[], matches=[])
        self.assertIsNone(av.employment)
        self.assertIsNone(av.installment)
        self.assertIsNone(av.agunan.npw)
        self.assertEqual(av.matching.rekap_per_bulan, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py::TestBuildApplicationView -v`
Expected: FAIL — `ImportError: cannot import name 'ApplicationView'`.

- [ ] **Step 3: Add `ApplicationView` to `models.py`**

Add after `ApplicationResult` (it references the view models + reuses domain models):

```python
class ApplicationView(BaseModel):
    """UI-shaped read-model for the assessment dashboard (the job result)."""
    documents: list[DocumentResult] = Field(default_factory=list)
    identity: IdentityView = Field(default_factory=IdentityView)
    employment: Optional[EmploymentView] = None
    agunan: AgunanView = Field(default_factory=AgunanView)
    installment: Optional[InstallmentView] = None
    matching: MatchingView = Field(default_factory=MatchingView)
    bank_statement: BankStatementView = Field(default_factory=BankStatementView)
    income: Optional[IncomeBreakdown] = None
    verification: VerificationInfo = Field(default_factory=VerificationInfo)
    decision: Optional[DecisionResult] = None
    audit: OrchestratorAudit = Field(default_factory=OrchestratorAudit)
```

- [ ] **Step 4: Add `build_application_view` to `view.py`**

Add `ApplicationResult, ApplicationView, MatchingView` to the models import.

```python
def build_application_view(
    result: ApplicationResult,
    *,
    agunan_input: Optional[AgunanInput],
    sk_response: Any,
    slip_docs: list[dict[str, Any]],
    credits: list[dict[str, Any]],
    matches: list,
) -> ApplicationView:
    """Project the domain ApplicationResult (+ echoed inputs + raw payloads) into
    the UI-shaped ApplicationView. Pure and total."""
    return ApplicationView(
        documents=result.documents,
        identity=project_identity(result.applicant.name),
        employment=project_employment(sk_response),
        agunan=project_agunan(result.collateral, agunan_input, result.fmv),
        installment=project_installment(result.income, result.decision),
        matching=MatchingView(
            transaksi_pemasukan=project_transaksi_pemasukan(credits),
            rekap_per_bulan=project_rekap(credits, slip_docs, matches),
            salary_slip=project_salary_slips(slip_docs),
        ),
        bank_statement=project_bank_statement(credits),
        income=result.income,
        verification=result.verification,
        decision=result.decision,
        audit=result.audit,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_view.py -v`
Expected: PASS (all classes).

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/view.py ocr_orchestrator/tests/test_view.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): ApplicationView + build_application_view assembler"
```

---

### Task 8: Request extension — new Form fields + `loan_amount = harga_rumah − dp`

**Files:**
- Modify: `ocr_orchestrator/api.py:148-203`
- Modify: `ocr_orchestrator/pipeline.py` (add the `agunan` keyword param to `run_job`/`_execute` so the endpoint call type-checks; the assemble-stage wiring that *uses* it lands in Task 9)
- Test: `ocr_orchestrator/tests/test_api.py`

The endpoint stops taking `loan_amount`; it takes `harga_rumah` + `dp` + tenor + rate and derives the loan. It also builds an `AgunanInput` and passes it to `run_job`. Because the endpoint acceptance tests invoke the **real** `run_job`, this task also adds the `agunan` param to `run_job`/`_execute` (accepted and threaded through; unused until Task 9).

- [ ] **Step 1: Write the failing tests (and repoint two existing api tests)**

`test_api.py` uses `unittest.TestCase` with `self.client` and `mock`. Add these methods to the `TestApi` class — unit-test the loan-derivation helper plus an endpoint acceptance test:

```python
    def test_build_loan_from_price_derives_amount(self):
        from ocr_orchestrator.api import _build_loan_from_price
        warnings = []
        loan = _build_loan_from_price(610_000_000.0, 200_000_000.0, 180, 0.105, warnings)
        self.assertEqual(loan.loan_amount, 410_000_000.0)   # harga - dp
        self.assertEqual(loan.tenor_months, 180)
        self.assertEqual(warnings, [])

    def test_build_loan_from_price_partial_warns(self):
        from ocr_orchestrator.api import _build_loan_from_price
        warnings = []
        self.assertIsNone(_build_loan_from_price(610_000_000.0, None, 180, 0.105, warnings))
        self.assertTrue(warnings)

    def test_accepts_harga_dp_address_returns_202(self):
        classify = _async([
            {"filename": "x.pdf", "document_type": "unknown", "confidence": "low"},
        ])
        with mock.patch.object(self.api.upstream, "classify_documents", classify):
            r = self.client.post(
                "/api/v1/applications",
                files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
                data={"luas_tanah": "96", "luas_bangunan": "45",
                      "kode_pos": "16969", "kelurahan": "Bojong Kulur",
                      "provinsi": "Jawa Barat", "kota_kab": "Bogor",
                      "harga_rumah": "610000000", "dp": "200000000",
                      "tenor_months": "180", "annual_interest_rate": "0.105"},
            )
            self.assertEqual(r.status_code, 202)
```

Repoint the two existing tests that assume `loan_amount` is an input:

- Replace `test_invalid_loan_amount_is_400` (it posts `loan_amount: -5`, which is no longer a field) with a `harga_rumah` validation test:

```python
    def test_invalid_harga_rumah_is_400(self):
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"harga_rumah": "-5"},
        )
        self.assertEqual(r.status_code, 400)
```

- Delete `test_accepts_collateral_and_loan_fields_returns_202` (it sends `loan_amount`); `test_accepts_harga_dp_address_returns_202` above replaces it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_api.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_loan_from_price'`, and `test_invalid_harga_rumah_is_400` returns 202 instead of 400 (harga_rumah not validated yet).

- [ ] **Step 3: Update `models` import + `api.py` signature and body**

In `api.py`, extend the import:

```python
from .models import (
    AcceptedResponse, AgunanInput, CollateralInput, JobStatusResponse, LoanRequest,
)
```

Replace the loan/collateral Form params and the build block in `create_application` (around lines 153-195). Remove the `loan_amount` Form param; add `harga_rumah`, `dp`, `provinsi`, `kota_kab`, `kecamatan`:

```python
    luas_tanah: Optional[float] = Form(None, description="Collateral land area m^2 (> 0)."),
    luas_bangunan: Optional[float] = Form(None, description="Collateral building area m^2 (>= 0)."),
    kode_pos: Optional[str] = Form(None, description="Collateral postal code."),
    kelurahan: Optional[str] = Form(None, description="Collateral village/ward."),
    provinsi: Optional[str] = Form(None, description="Agunan province."),
    kota_kab: Optional[str] = Form(None, description="Agunan city/regency."),
    kecamatan: Optional[str] = Form(None, description="Agunan district."),
    appraisal_month: Optional[int] = Form(None, description="Appraisal month YYYYMM."),
    harga_rumah: Optional[float] = Form(None, description="Listed house price (> 0)."),
    dp: Optional[float] = Form(None, description="Down payment (>= 0)."),
    tenor_months: Optional[int] = Form(None, description="Loan term in months (> 0)."),
    annual_interest_rate: Optional[float] = Form(None, description="Annual rate, e.g. 0.105 (>= 0)."),
```

Replace the validation + build block:

```python
    _validate_numeric("luas_tanah", luas_tanah, allow_zero=False)
    _validate_numeric("luas_bangunan", luas_bangunan, allow_zero=True)
    _validate_numeric("harga_rumah", harga_rumah, allow_zero=False)
    _validate_numeric("dp", dp, allow_zero=True)
    _validate_numeric("tenor_months", tenor_months, allow_zero=False)
    _validate_numeric("annual_interest_rate", annual_interest_rate, allow_zero=True)
    _validate_appraisal_month(appraisal_month)

    input_warnings: list[str] = []
    collateral = _build_collateral(luas_tanah, luas_bangunan, kode_pos, kelurahan,
                                   appraisal_month, input_warnings)
    loan = _build_loan_from_price(harga_rumah, dp, tenor_months,
                                  annual_interest_rate, input_warnings)
    agunan = AgunanInput(provinsi=provinsi, kota_kab=kota_kab,
                         kecamatan=kecamatan, harga_rumah=harga_rumah)

    job = await store.create()
    task = asyncio.create_task(
        run_job(store, job.id, payload, bonus_accept_pct=pct, password=password,
                collateral=collateral, loan=loan, agunan=agunan,
                input_warnings=input_warnings)
    )
```

Replace `_build_loan` with a price-based builder:

```python
def _build_loan_from_price(
    harga_rumah: float | None, dp: float | None, tenor_months: int | None,
    annual_interest_rate: float | None, warnings: list[str],
) -> LoanRequest | None:
    """loan_amount = harga_rumah - dp (D3). All four fields required for a loan."""
    fields = (harga_rumah, dp, tenor_months, annual_interest_rate)
    if all(v is not None for v in fields):
        return LoanRequest(loan_amount=harga_rumah - dp, tenor_months=tenor_months,
                           annual_interest_rate=annual_interest_rate)
    if any(v is not None for v in fields):
        warnings.append("Partial loan fields provided (need harga_rumah, dp, "
                        "tenor_months and annual_interest_rate); decision skipped.")
    return None
```

Then add the `agunan` param to `pipeline.py` so the endpoint's `run_job(...)` call type-checks. Add `AgunanInput` to the pipeline's `from .models import (...)` block, and add `agunan: AgunanInput | None = None` (keyword-only) to **both** `run_job` and `_execute`, threading it from `run_job` into the `_execute(...)` call. It is unused until Task 9.

```python
# ocr_orchestrator/pipeline.py — run_job signature (mirror the same param on _execute)
async def run_job(
    store: JobStore,
    job_id: str,
    files: list[tuple[str, bytes]],
    *,
    bonus_accept_pct: float,
    password: str | None,
    collateral: CollateralInput | None = None,
    loan: LoanRequest | None = None,
    agunan: AgunanInput | None = None,
    input_warnings: list[str] | None = None,
) -> None:
```

In `run_job`, pass `agunan=agunan` into the existing `await _execute(...)` call.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_api.py -v`
Expected: PASS (the two `_build_loan_from_price` tests, `test_invalid_harga_rumah_is_400`, and `test_accepts_harga_dp_address_returns_202`).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/api.py ocr_orchestrator/pipeline.py ocr_orchestrator/tests/test_api.py
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): request takes harga_rumah/dp/address; loan_amount derived"
```

---

### Task 9: Pipeline wiring — assemble builds & stores `ApplicationView`

**Files:**
- Modify: `ocr_orchestrator/pipeline.py:60-99,238-257`, `ocr_orchestrator/models.py:191-197`
- Test: `ocr_orchestrator/tests/test_pipeline.py`

- [ ] **Step 1: Repoint the existing pipeline assertions to `ApplicationView`**

`ApplicationView` exposes `identity` (not `applicant`) and `agunan.fmv`/`agunan.npw` (not top-level `fmv`); `income`/`verification`/`decision`/`documents`/`audit` are reused unchanged. Edit `test_pipeline.py`:

In `test_happy_path_bank_verified`:
- Replace `self.assertEqual(job.result.applicant.name, "BUDI")` with
  `self.assertEqual(job.result.identity.ktp.nama, "BUDI")`.
- Delete `self.assertEqual(job.result.applicant.name_source, "slip")` (name_source is not surfaced in the view; name resolution stays covered by `test_identity.py`).
- Add the new view assertions (the `income`, `verification`, `documents`/`extracted`, and `monthly_breakdown` assertions stay — those fields are reused on the view):

```python
        from ocr_orchestrator.models import ApplicationView
        self.assertIsInstance(job.result, ApplicationView)
        self.assertEqual(job.result.installment.gaji_bulanan, 9_500_000)
        self.assertEqual(len(job.result.matching.salary_slip), 1)
```

In `test_fmv_and_decide_run_when_inputs_present`:
- Replace `self.assertEqual(job.result.fmv.fair_value, 1_000_000_000)` with
  `self.assertEqual(job.result.agunan.npw, 1_000_000_000)`  (npw == fmv.fair_value).
- `self.assertEqual(job.result.decision.recommendation, "eligible")` stays.

In `test_stages_skipped_when_no_collateral_or_loan`:
- Replace `self.assertIsNone(job.result.fmv)` with `self.assertIsNone(job.result.agunan.npw)`.
- `self.assertIsNone(job.result.decision)` stays.

`test_ocr_match_down_degrades_to_no_income` and `test_input_warnings_land_in_audit` need no change (`income`, `audit` are reused on the view).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_pipeline.py -v`
Expected: FAIL — `AttributeError: 'ApplicationResult' object has no attribute 'identity'` (the stored result is still the domain `ApplicationResult`).

- [ ] **Step 3: Wire the projector into `pipeline.py`**

The `agunan` param on `run_job`/`_execute` and the `AgunanInput` models import were already added in Task 8. Now add the projector import at the top of `pipeline.py`:

```python
from . import view
```

At the end of `_execute` (Stage 7 assemble), after `result = ApplicationResult(...)` is built, replace `await store.set_result(job_id, result)` with project-then-store:

```python
    view_result = view.build_application_view(
        result,
        agunan_input=agunan,
        sk_response=sk_response or None,
        slip_docs=slip_docs,
        credits=credits,
        matches=matches,
    )
    await store.set_result(job_id, view_result)
```

In `models.py`, change `JobStatusResponse.result`:

```python
    result: Optional[ApplicationView] = None
```

- [ ] **Step 4: Run the orchestrator test suite**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests -v`
Expected: PASS. Fix any remaining old-shape assertions by repointing them to `ApplicationView` — `income`/`verification`/`decision`/`audit`/`documents` are at the top level; `fmv` is under `agunan.fmv`, and `applicant.name` is under `identity.ktp.nama`.

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/pipeline.py ocr_orchestrator/models.py ocr_orchestrator/tests
git -c core.logAllRefUpdates=false commit -m "feat(orchestrator): assemble stage builds & serves ApplicationView"
```

---

### Task 10: Degradation test — `ocr_match` down still renders agunan/fmv/decision

**Files:**
- Test: `ocr_orchestrator/tests/test_pipeline.py`

- [ ] **Step 1: Write the test**

Add this method to the `TestRunJob` class in `test_pipeline.py` (it mirrors `test_ocr_match_down_degrades_to_no_income` but supplies collateral + loan + agunan + an FMV mock, then asserts the view still renders agunan/decision):

```python
    async def test_match_outage_still_renders_agunan_and_decision(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        from ocr_orchestrator.models import AgunanInput, CollateralInput, LoanRequest
        collateral = CollateralInput(luas_tanah=80.0, luas_bangunan=50.0)
        loan = LoanRequest(loan_amount=410_000_000, tenor_months=180,
                           annual_interest_rate=0.105)
        agunan = AgunanInput(provinsi="Jawa Barat", harga_rumah=610_000_000.0)
        fmv = _async({"land_value": 3.0, "building_value": 2.0,
                      "fair_value": 610_000_000.0, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async_raise(UpstreamUnreachableError("ocr_match down"))), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan,
                                   agunan=agunan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.agunan.npw, 610_000_000.0)        # FMV still ran
        self.assertEqual(job.result.decision.recommendation, "refer_to_analyst")
        self.assertEqual(job.result.matching.rekap_per_bulan, [])     # no income data
        self.assertEqual(job.result.bank_statement.n_transaksi, 0)
        self.assertIsNone(job.result.installment.kemampuan_bayar)     # qi is None
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_pipeline.py::TestRunJob::test_match_outage_still_renders_agunan_and_decision -v`
Expected: PASS (after Task 9 wired the view; this test asserts the projector is total under a match outage).

- [ ] **Step 3: Run the full suite**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests -v`
Expected: PASS (all).

- [ ] **Step 4: Commit**

```bash
git add ocr_orchestrator/tests/test_pipeline.py
git -c core.logAllRefUpdates=false commit -m "test(orchestrator): ApplicationView renders under ocr_match outage (D1 degrade)"
```

---

## Final verification

- [ ] Run the whole orchestrator suite: `.venv\Scripts\python -m pytest ocr_orchestrator/tests -v` → all pass.
- [ ] Manual smoke (optional): launch the stack, `POST /api/v1/applications` with `harga_rumah`/`dp`/agunan + a slip + mutasi, poll, and confirm the result JSON has `identity`, `employment`, `agunan.npw`, `installment`, `matching.rekap_per_bulan`, `bank_statement`, `decision`.
- [ ] The demo `/upload` page still renders (it dumps the result JSON — now `ApplicationView`); updating that page's form/section rendering is **frontend work, out of scope** for this plan.

## Notes & deferrals

- Identity KTP/KK fields are `null` stubs (D2) — a future extractor service fills them; the contract shape is already stable.
- Bank-statement debit ledger is deferred (D5) — needs an `ocr_mutasi` passthrough change.
- The rekap `potongan`/`income_slip` formulas are the spec's inferred semantics; confirm against real `ocr_slip` output during Task 5 and adjust the two lines if the slip carries explicit `thr`/`bonus` fields.
