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


if __name__ == "__main__":
    unittest.main()
