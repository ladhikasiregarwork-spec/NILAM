import unittest

from ocr_orchestrator.jobs import JobStore


class TestJobStore(unittest.IsolatedAsyncioTestCase):
    async def test_create_and_get(self):
        store = JobStore(retention=10)
        job = await store.create()
        self.assertEqual(job.status, "pending")
        self.assertEqual([s.name for s in job.stages],
                         ["classify", "extract", "verify", "aggregate", "fmv", "decide"])
        fetched = await store.get(job.id)
        self.assertIs(fetched, job)

    async def test_get_unknown_returns_none(self):
        store = JobStore(retention=10)
        self.assertIsNone(await store.get("nope"))

    async def test_set_stage_and_status(self):
        store = JobStore(retention=10)
        job = await store.create()
        await store.set_status(job.id, "running")
        await store.set_stage(job.id, "classify", "completed")
        self.assertEqual(job.status, "running")
        stage = next(s for s in job.stages if s.name == "classify")
        self.assertEqual(stage.status, "completed")

    async def test_fail_sets_error_and_status(self):
        store = JobStore(retention=10)
        job = await store.create()
        await store.fail(job.id, "boom")
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error, "boom")

    async def test_set_result_marks_completed(self):
        from ocr_orchestrator.models import (
            ApplicantInfo, ApplicationResult, IncomeBreakdown,
            OrchestratorAudit, VerificationInfo,
        )
        store = JobStore(retention=10)
        job = await store.create()
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
        await store.set_result(job.id, result)
        self.assertEqual(job.status, "completed")
        self.assertIs(job.result, result)

    async def test_retention_evicts_oldest(self):
        store = JobStore(retention=2)
        a = await store.create()
        b = await store.create()
        c = await store.create()
        self.assertIsNone(await store.get(a.id))   # evicted
        self.assertIsNotNone(await store.get(b.id))
        self.assertIsNotNone(await store.get(c.id))


if __name__ == "__main__":
    unittest.main()
