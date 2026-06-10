import unittest
from unittest import mock

from ocr_orchestrator import verify


class _FakeSettings:
    match_amount_tolerance_rp = 1.0


class TestVerify(unittest.TestCase):
    def setUp(self):
        # match_all reads tolerance from ocr_match.config via this name.
        patcher = mock.patch("ocr_match.matcher.get_settings",
                             return_value=_FakeSettings())
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_exact_amount_next_month_match(self):
        slip_docs = [{"source_file": "Slip_Feb_2025.pdf",
                      "worker_name": "BUDI", "total_paid": 9_500_000.0,
                      "period": "2025-02"}]
        gaji = [{"source_file": "Mar.pdf", "tanggal": "2025-03-25",
                 "keterangan": "GAJI", "amount": 9_500_000.0, "page": 1,
                 "category": "Gaji"}]
        matches, verified_months = verify.verify_slips_credits(slip_docs, gaji)
        self.assertEqual(len(matches), 1)
        self.assertEqual(verified_months, {"2025-03"})

    def test_no_match_returns_empty_verified(self):
        slip_docs = [{"source_file": "s.pdf", "total_paid": 1_000_000.0,
                      "period": "2025-02"}]
        gaji = [{"source_file": "m.pdf", "tanggal": "2025-03-25",
                 "keterangan": "GAJI", "amount": 9_999_999.0, "page": 1,
                 "category": "Gaji"}]
        matches, verified_months = verify.verify_slips_credits(slip_docs, gaji)
        self.assertEqual(matches, [])
        self.assertEqual(verified_months, set())

    def test_empty_inputs(self):
        matches, verified_months = verify.verify_slips_credits([], [])
        self.assertEqual(matches, [])
        self.assertEqual(verified_months, set())


if __name__ == "__main__":
    unittest.main()
