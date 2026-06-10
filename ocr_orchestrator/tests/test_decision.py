import unittest

from ocr_orchestrator.decision import compute_installment, decide
from ocr_orchestrator.models import FmvResult, IncomeBreakdown, LoanRequest

THRESH = dict(max_ltv=0.80, max_dsr=0.50, existing_installment=0.0)


def _income(monthly, basis):
    return IncomeBreakdown(
        n_statement_months=12, avg_monthly_gaji_insentif=monthly or 0.0,
        monthly_thr=0.0, bonus_total=0.0, bonus_accept_pct=0.0, bonus_monthly=0.0,
        monthly_qualifying_income=monthly, basis=basis,
        verified_month_count=12, warnings=[],
    )


def _fmv(fair_value, location_matched=True, warnings=None):
    return FmvResult(land_value=fair_value, building_value=0.0,
                     fair_value=fair_value, location_matched=location_matched,
                     backend="linear", warnings=warnings or [])


def _loan(amount, tenor=240, rate=0.10):
    return LoanRequest(loan_amount=amount, tenor_months=tenor,
                       annual_interest_rate=rate)


class TestComputeInstallment(unittest.TestCase):
    def test_zero_rate_is_principal_over_tenor(self):
        m = compute_installment(LoanRequest(
            loan_amount=120_000_000, tenor_months=120, annual_interest_rate=0.0))
        self.assertEqual(m, 1_000_000)

    def test_annuity_matches_formula(self):
        loan = LoanRequest(loan_amount=100_000_000, tenor_months=12,
                           annual_interest_rate=0.12)
        r = 0.12 / 12
        n = 12
        expected = 100_000_000 * r * (1 + r) ** n / ((1 + r) ** n - 1)
        self.assertAlmostEqual(compute_installment(loan), expected, places=2)


class TestDecide(unittest.TestCase):
    def test_eligible_when_checks_pass_and_bank_verified(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertTrue(out.dsr.passed)
        self.assertEqual(out.recommendation, "eligible")
        self.assertEqual(out.existing_installment, 0.0)

    def test_refer_when_checks_pass_but_income_not_bank_verified(self):
        out = decide(income=_income(20_000_000, "slip_fallback"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertTrue(out.dsr.passed)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_not_eligible_when_ltv_exceeds_cap(self):
        out = decide(income=_income(50_000_000, "bank_verified"),
                     fmv=_fmv(500_000_000), loan=_loan(450_000_000), **THRESH)
        self.assertFalse(out.ltv.passed)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_not_eligible_when_dsr_exceeds_cap(self):
        out = decide(income=_income(2_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertTrue(out.ltv.passed)
        self.assertFalse(out.dsr.passed)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_refer_when_no_fmv(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=None, loan=_loan(700_000_000), **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")
        self.assertIsNone(out.ltv)
        self.assertIsNone(out.dsr)

    def test_refer_when_no_loan(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000), loan=None, **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_refer_when_income_is_none(self):
        out = decide(income=_income(None, "none"),
                     fmv=_fmv(1_000_000_000), loan=_loan(700_000_000), **THRESH)
        self.assertEqual(out.recommendation, "refer_to_analyst")

    def test_zero_fair_value_fails_ltv(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(0.0), loan=_loan(700_000_000), **THRESH)
        self.assertFalse(out.ltv.passed)
        self.assertIsNone(out.ltv.value)
        self.assertEqual(out.recommendation, "not_eligible")

    def test_fmv_warnings_flow_into_decision(self):
        out = decide(income=_income(20_000_000, "bank_verified"),
                     fmv=_fmv(1_000_000_000, location_matched=False,
                              warnings=["medians fallback"]),
                     loan=_loan(700_000_000), **THRESH)
        self.assertIn("medians fallback", out.warnings)
        self.assertTrue(any("location not matched" in w.lower() for w in out.warnings))


if __name__ == "__main__":
    unittest.main()
