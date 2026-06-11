import unittest

from ocr_orchestrator.slip_dates import credit_month, slip_month


class TestSlipMonth(unittest.TestCase):
    def test_period_wins(self):
        self.assertEqual(slip_month({"period": "2025-02",
                                     "source_file": "Apr_2025.pdf"}), "2025-02")

    def test_filename_month_name(self):
        self.assertEqual(slip_month({"source_file": "Slip_Februari_2025.pdf"}),
                         "2025-02")

    def test_filename_iso(self):
        self.assertEqual(slip_month({"source_file": "payslip_2025-04.pdf"}), "2025-04")

    def test_none_when_unparseable(self):
        self.assertIsNone(slip_month({"source_file": "payslip.pdf"}))


class TestCreditMonth(unittest.TestCase):
    def test_slice(self):
        self.assertEqual(credit_month("2025-03-25"), "2025-03")

    def test_short_string(self):
        self.assertIsNone(credit_month("2025"))


if __name__ == "__main__":
    unittest.main()
