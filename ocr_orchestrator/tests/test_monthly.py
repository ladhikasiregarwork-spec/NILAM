import unittest
from types import SimpleNamespace

from ocr_orchestrator.monthly import build_monthly_breakdown


def _credit(category, amount, tanggal, source_file="mut.pdf"):
    return {
        "source_file": source_file, "tanggal": tanggal,
        "keterangan": category.upper(), "amount": amount,
        "page": 1, "category": category,
    }


def _slip(source_file, total_paid, deduction=0.0, pokok=0.0,
          incentive=0.0, period=None):
    return {
        "source_file": source_file, "total_paid": total_paid,
        "deduction": deduction, "pokok": pokok, "incentive": incentive,
        "period": period,
    }


def _match(slip_source_file, credit_month):
    """Minimal stand-in for ocr_match.models.MatchPair.

    build_monthly_breakdown only reads pair.slip.source_file and
    pair.credit.month; the real MatchPair shape is covered by the
    pipeline end-to-end test.
    """
    return SimpleNamespace(
        slip=SimpleNamespace(source_file=slip_source_file),
        credit=SimpleNamespace(month=credit_month),
    )


def _by_month(rows):
    return {r.month: r for r in rows}


class TestBuildMonthlyBreakdown(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(build_monthly_breakdown([], [], []), [])

    def test_bank_verified_row(self):
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-03")]
        matches = [_match("slip.pdf", "2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.month, "2026-03")
        self.assertEqual(r.source, "bank_verified")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.bank_salary_credit, 8_000_000)
        self.assertEqual(r.thr, 0.0)               # bank row, no THR -> real 0
        self.assertEqual(r.bonus_non_fixed, 0.0)
        self.assertEqual(r.deduction, 750_000)     # from slip
        self.assertEqual(r.total_paid, 7_250_000)

    def test_bank_unverified_row_unmatched_slip_same_month(self):
        # Gaji credit + a slip for the same period that did NOT match.
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches=[])
        r = _by_month(rows)["2026-03"]
        self.assertEqual(r.source, "bank_unverified")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.deduction, 750_000)     # slip still attached
        self.assertEqual(r.total_paid, 7_250_000)

    def test_bank_only_row_nulls_slip_fields(self):
        credits = [_credit("Gaji", 8_000_000, "2026-04-25"),
                   _credit("THR", 8_000_000, "2026-04-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-04"]
        self.assertEqual(r.source, "bank_only")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.thr, 8_000_000)
        self.assertIsNone(r.deduction)             # no slip -> null
        self.assertIsNone(r.total_paid)

    def test_thr_only_month_fixed_is_zero_not_null(self):
        credits = [_credit("THR", 8_000_000, "2026-04-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-04"]
        self.assertEqual(r.source, "bank_only")
        self.assertEqual(r.fixed_routine_income, 0.0)   # statement covered it -> 0
        self.assertEqual(r.bank_salary_credit, 0.0)
        self.assertEqual(r.thr, 8_000_000)

    def test_slip_only_row(self):
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       pokok=6_500_000, incentive=1_500_000, period="2026-05")]
        rows = build_monthly_breakdown(credits=[], slip_docs=slips, matches=[])
        r = _by_month(rows)["2026-05"]
        self.assertEqual(r.source, "slip_only")
        self.assertEqual(r.fixed_routine_income, 6_500_000)   # slip pokok
        self.assertEqual(r.bonus_non_fixed, 1_500_000)        # slip incentive
        self.assertIsNone(r.thr)                              # slip can't split
        self.assertIsNone(r.bank_salary_credit)              # no bank data
        self.assertEqual(r.deduction, 750_000)
        self.assertEqual(r.total_paid, 7_250_000)

    def test_insentif_goes_to_non_fixed(self):
        credits = [_credit("Gaji", 8_000_000, "2026-03-25"),
                   _credit("Insentif", 500_000, "2026-03-25"),
                   _credit("Bonus", 1_000_000, "2026-03-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-03"]
        self.assertEqual(r.fixed_routine_income, 8_000_000)        # Gaji only
        self.assertEqual(r.bonus_non_fixed, 1_500_000)            # Bonus + Insentif

    def test_lainnya_does_not_create_a_row(self):
        credits = [_credit("Lainnya", 50_000, "2026-03-02")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        self.assertEqual(rows, [])

    def test_x_plus_1_homing_puts_slip_in_credit_month(self):
        # Slip period 2026-02, matched to a bank Gaji credit dated 2026-03.
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-02")]
        matches = [_match("slip.pdf", "2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches)
        self.assertEqual([r.month for r in rows], ["2026-03"])    # not 2026-02
        r = rows[0]
        self.assertEqual(r.source, "bank_verified")
        self.assertEqual(r.deduction, 750_000)

    def test_rows_sorted_ascending(self):
        credits = [_credit("Gaji", 1, "2026-03-25"),
                   _credit("Gaji", 1, "2026-01-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        self.assertEqual([r.month for r in rows], ["2026-01", "2026-03"])

    def test_multiple_slips_same_month_sum(self):
        slips = [
            _slip("a.pdf", total_paid=1_000_000, deduction=100_000, period="2026-05"),
            _slip("b.pdf", total_paid=2_000_000, deduction=200_000, period="2026-05"),
        ]
        rows = build_monthly_breakdown(credits=[], slip_docs=slips, matches=[])
        r = _by_month(rows)["2026-05"]
        self.assertEqual(r.deduction, 300_000)
        self.assertEqual(r.total_paid, 3_000_000)


if __name__ == "__main__":
    unittest.main()
