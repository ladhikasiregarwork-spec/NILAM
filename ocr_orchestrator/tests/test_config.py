import unittest

from ocr_orchestrator.config import Settings


class TestSettings(unittest.TestCase):
    def test_defaults(self):
        # Build directly (bypass .env) to assert the shipped defaults.
        s = Settings(_env_file=None)
        self.assertEqual(s.app_port, 8500)
        self.assertEqual(s.ocr_classifier_url, "http://127.0.0.1:5001")
        self.assertEqual(s.ocr_match_url, "http://127.0.0.1:5005")
        self.assertEqual(s.ocr_sk_url, "http://127.0.0.1:5002")
        self.assertEqual(s.default_bonus_accept_pct, 0.0)
        self.assertEqual(s.job_retention, 200)
        self.assertEqual(s.max_files, 50)

    def test_bonus_pct_is_float(self):
        s = Settings(_env_file=None)
        self.assertIsInstance(s.default_bonus_accept_pct, float)

    def test_fmv_and_decision_defaults(self):
        s = Settings(_env_file=None)
        self.assertEqual(s.fmv_url, "http://127.0.0.1:8000")
        self.assertEqual(s.fmv_timeout_s, 30.0)
        self.assertEqual(s.max_ltv, 0.80)
        self.assertEqual(s.max_dsr, 0.50)
        self.assertEqual(s.default_existing_installment, 0.0)


if __name__ == "__main__":
    unittest.main()
