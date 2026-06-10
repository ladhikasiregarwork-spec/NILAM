import unittest

from ocr_orchestrator.identity import resolve_applicant_name


class TestResolveApplicantName(unittest.TestCase):
    def test_prefers_slip(self):
        name, src = resolve_applicant_name(
            slip_docs=[{"worker_name": "BUDI SANTOSO"}],
            mutasi_accounts=[{"nama": "B SANTOSO"}],
            sk_responses=[{"summary": {"worker_name": "BUDI"}}],
        )
        self.assertEqual(name, "BUDI SANTOSO")
        self.assertEqual(src, "slip")

    def test_falls_back_to_mutasi(self):
        name, src = resolve_applicant_name(
            slip_docs=[{"worker_name": None}],
            mutasi_accounts=[{"nama": "SITI AMINAH"}],
            sk_responses=[],
        )
        self.assertEqual(name, "SITI AMINAH")
        self.assertEqual(src, "mutasi")

    def test_falls_back_to_sk_nested(self):
        name, src = resolve_applicant_name(
            slip_docs=[],
            mutasi_accounts=[],
            sk_responses=[{"summary": {"dokumen": [{"nama_pekerja": "AGUS"}]}}],
        )
        self.assertEqual(name, "AGUS")
        self.assertEqual(src, "sk")

    def test_none_when_nothing(self):
        name, src = resolve_applicant_name([], [], [])
        self.assertIsNone(name)
        self.assertIsNone(src)


if __name__ == "__main__":
    unittest.main()
