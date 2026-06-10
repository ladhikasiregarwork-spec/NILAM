import unittest

from ocr_orchestrator.income import compute_income


def _credit(category, amount, tanggal):
    return {"category": category, "amount": amount, "tanggal": tanggal}


class TestComputeIncome(unittest.TestCase):
    def test_bank_verified_full_formula(self):
        # 2 months of Gaji 10,000,000 + Insentif 500,000; one THR 12,000,000;
        # one Bonus 24,000,000; analyst accepts 50% of bonus.
        credits = [
            _credit("Gaji", 10_000_000, "2025-01-25"),
            _credit("Insentif", 500_000, "2025-01-25"),
            _credit("Gaji", 10_000_000, "2025-02-25"),
            _credit("Insentif", 500_000, "2025-02-25"),
            _credit("THR", 12_000_000, "2025-02-25"),
            _credit("Bonus", 24_000_000, "2025-02-25"),
        ]
        out = compute_income(
            credits=credits,
            verified_months={"2025-01", "2025-02"},
            slip_total_paids=[10_500_000.0],
            bonus_accept_pct=0.5,
        )
        self.assertEqual(out.basis, "bank_verified")
        self.assertEqual(out.n_statement_months, 2)
        self.assertEqual(out.avg_monthly_gaji_insentif, 10_500_000)   # (21,000,000)/2
        self.assertEqual(out.monthly_thr, 1_000_000)                  # 12,000,000/12
        self.assertEqual(out.bonus_total, 24_000_000)
        self.assertEqual(out.bonus_monthly, 1_000_000)                # 24,000,000*0.5/12
        self.assertEqual(out.monthly_qualifying_income, 12_500_000)
        self.assertEqual(out.verified_month_count, 2)

    def test_bonus_excluded_at_zero_pct(self):
        credits = [_credit("Gaji", 9_000_000, "2025-03-25"),
                   _credit("Bonus", 60_000_000, "2025-03-25")]
        out = compute_income(credits=credits, verified_months={"2025-03"},
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.bonus_total, 60_000_000)
        self.assertEqual(out.bonus_monthly, 0.0)
        self.assertEqual(out.monthly_qualifying_income, 9_000_000)

    def test_bank_unverified_when_no_match(self):
        credits = [_credit("Gaji", 8_000_000, "2025-04-25")]
        out = compute_income(credits=credits, verified_months=set(),
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "bank_unverified")
        self.assertEqual(out.verified_month_count, 0)
        self.assertEqual(out.monthly_qualifying_income, 8_000_000)

    def test_n_months_counts_distinct_credit_months_not_calendar_span(self):
        # Gaji in Jan and Mar only (Feb skipped). Denominator must be 2, not 3.
        credits = [_credit("Gaji", 10_000_000, "2025-01-25"),
                   _credit("Gaji", 10_000_000, "2025-03-25")]
        out = compute_income(credits=credits, verified_months={"2025-01"},
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.n_statement_months, 2)
        self.assertEqual(out.avg_monthly_gaji_insentif, 10_000_000)

    def test_slip_fallback_when_no_mutasi(self):
        out = compute_income(credits=[], verified_months=set(),
                             slip_total_paids=[7_000_000.0, 9_000_000.0],
                             bonus_accept_pct=0.5)
        self.assertEqual(out.basis, "slip_fallback")
        self.assertEqual(out.avg_monthly_gaji_insentif, 8_000_000)   # mean of the two slips
        self.assertEqual(out.monthly_thr, 0.0)
        self.assertEqual(out.bonus_monthly, 0.0)
        self.assertEqual(out.monthly_qualifying_income, 8_000_000)
        self.assertTrue(out.warnings)

    def test_none_when_nothing(self):
        out = compute_income(credits=[], verified_months=set(),
                             slip_total_paids=[], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "none")
        self.assertIsNone(out.monthly_qualifying_income)
        self.assertTrue(out.warnings)

    def test_mutasi_present_but_no_salary_credits_falls_back_to_slip(self):
        # Only Lainnya credits -> no Gaji/Insentif months -> use slip.
        credits = [_credit("Lainnya", 50_000, "2025-05-02")]
        out = compute_income(credits=credits, verified_months=set(),
                             slip_total_paids=[6_000_000.0], bonus_accept_pct=0.0)
        self.assertEqual(out.basis, "slip_fallback")
        self.assertEqual(out.monthly_qualifying_income, 6_000_000)


if __name__ == "__main__":
    unittest.main()
