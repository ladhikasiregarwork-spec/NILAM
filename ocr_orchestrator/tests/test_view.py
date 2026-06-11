# ocr_orchestrator/tests/test_view.py
import unittest
from types import SimpleNamespace

from ocr_orchestrator import view
from ocr_orchestrator.models import AgunanInput, AgunanView, CollateralInput, FmvResult, EmploymentView, IdentityView
from ocr_orchestrator.models import (  # extend the model imports
    DecisionResult, InstallmentView, IncomeBreakdown,
)
from ocr_orchestrator.models import CreditView, MatchingView, RekapRow, SlipView


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
        self.assertIsNone(rows[0].gaji_mutasi)
        self.assertIsNone(rows[0].thr_mutasi)

    def test_rekap_insentif_folds_into_bonus_mutasi(self):
        credits = [_credit("Bonus", 1_000.0, "2026-03-17"),
                   _credit("Insentif", 500.0, "2026-03-10")]
        rows = view.project_rekap(credits, [], [])
        self.assertEqual(rows[0].bonus_mutasi, 1_500.0)
