# ocr_orchestrator/tests/test_view.py
import unittest

from ocr_orchestrator import view
from ocr_orchestrator.models import EmploymentView, IdentityView


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
