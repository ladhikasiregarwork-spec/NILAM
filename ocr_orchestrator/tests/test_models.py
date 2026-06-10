import unittest

from ocr_orchestrator.models import (
    ApplicantInfo,
    ApplicationResult,
    DocumentResult,
    IncomeBreakdown,
    JobStage,
    JobStatusResponse,
    OrchestratorAudit,
    VerificationInfo,
)


class TestModels(unittest.TestCase):
    def test_document_result_defaults(self):
        d = DocumentResult(filename="a.pdf", document_type="mutasi",
                           confidence="high", status="extracted")
        self.assertIsNone(d.extracted)

    def test_applicant_reserved_fields_default_null(self):
        a = ApplicantInfo(name="BUDI SANTOSO", name_source="slip")
        self.assertIsNone(a.birth_date)
        self.assertIsNone(a.age)
        self.assertIsNone(a.nik)

    def test_job_stage_default_pending(self):
        s = JobStage(name="classify")
        self.assertEqual(s.status, "pending")
        self.assertIsNone(s.error)

    def test_application_result_assembles(self):
        result = ApplicationResult(
            documents=[],
            applicant=ApplicantInfo(),
            income=IncomeBreakdown(
                n_statement_months=0, avg_monthly_gaji_insentif=0.0,
                monthly_thr=0.0, bonus_total=0.0, bonus_accept_pct=0.0,
                bonus_monthly=0.0, monthly_qualifying_income=None,
                basis="none", verified_month_count=0, warnings=[],
            ),
            verification=VerificationInfo(),
            audit=OrchestratorAudit(),
        )
        self.assertEqual(result.income.basis, "none")

    def test_job_status_response_optional_result(self):
        r = JobStatusResponse(job_id="x", status="pending",
                              stages=[JobStage(name="classify")])
        self.assertIsNone(r.result)
        self.assertIsNone(r.error)


class TestMonthlyIncomeRow(unittest.TestCase):
    def test_row_validates_and_allows_nulls(self):
        from ocr_orchestrator.models import MonthlyIncomeRow

        row = MonthlyIncomeRow(
            month="2026-04",
            fixed_routine_income=8_000_000.0,
            thr=8_000_000.0,
            bonus_non_fixed=0.0,
            deduction=None,
            total_paid=None,
            bank_salary_credit=8_000_000.0,
            source="bank_only",
        )
        self.assertEqual(row.month, "2026-04")
        self.assertIsNone(row.deduction)
        self.assertEqual(row.source, "bank_only")

    def test_income_breakdown_has_empty_breakdown_by_default(self):
        ib = IncomeBreakdown(
            n_statement_months=0,
            avg_monthly_gaji_insentif=0.0,
            monthly_thr=0.0,
            bonus_total=0.0,
            bonus_accept_pct=0.0,
            bonus_monthly=0.0,
            monthly_qualifying_income=None,
            basis="none",
            verified_month_count=0,
        )
        self.assertEqual(ib.monthly_breakdown, [])


if __name__ == "__main__":
    unittest.main()
