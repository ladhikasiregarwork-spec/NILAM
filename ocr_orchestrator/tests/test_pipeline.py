import unittest
from unittest import mock

from ocr_orchestrator import pipeline
from ocr_orchestrator.jobs import JobStore


class _FakeMatchSettings:
    match_amount_tolerance_rp = 1.0


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


def _async_raise(exc):
    async def _fn(*args, **kwargs):
        raise exc
    return _fn


class TestRunJob(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p = mock.patch("ocr_match.matcher.get_settings",
                       return_value=_FakeMatchSettings())
        self.addCleanup(p.stop)
        p.start()

    async def test_happy_path_bank_verified(self):
        files = [("slip_feb.pdf", b"a"), ("mut_mar.pdf", b"b")]
        classify = _async([
            {"filename": "slip_feb.pdf", "document_type": "slip", "confidence": "high"},
            {"filename": "mut_mar.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        slips = _async([{"source_file": "slip_feb.pdf#page-1", "worker_name": "BUDI",
                         "total_paid": 9_500_000.0, "period": "2025-02"}])
        mutasi = _async({
            "files": [{"filename": "mut_mar.pdf",
                       "account": {"nama": "BUDI SANTOSO"}}],
            "credits": [{"source_file": "mut_mar.pdf", "tanggal": "2025-03-25",
                         "keterangan": "GAJI", "amount": 9_500_000.0, "page": 1,
                         "category": "Gaji"}],
            "audit": {},
        })
        sk = _async({"summary": {}})

        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)

        self.assertEqual(job.status, "completed")
        self.assertIsNotNone(job.result)
        self.assertEqual(job.result.income.basis, "bank_verified")
        self.assertEqual(job.result.income.monthly_qualifying_income, 9_500_000)
        self.assertEqual(job.result.applicant.name, "BUDI")
        self.assertEqual(job.result.applicant.name_source, "slip")
        self.assertEqual(job.result.verification.verified_month_count, 1)

        slip_doc = next(d for d in job.result.documents if d.document_type == "slip")
        self.assertIsNotNone(slip_doc.extracted)
        self.assertEqual(slip_doc.extracted["worker_name"], "BUDI")

        # --- monthly breakdown is populated end-to-end ---
        breakdown = job.result.income.monthly_breakdown
        self.assertEqual(len(breakdown), 1)
        row = breakdown[0]
        self.assertEqual(row.month, "2025-03")          # homed to the bank credit month
        self.assertEqual(row.source, "bank_verified")
        self.assertEqual(row.fixed_routine_income, 9_500_000)
        self.assertEqual(row.bank_salary_credit, 9_500_000)
        self.assertEqual(row.total_paid, 9_500_000)     # from the matched slip
        self.assertEqual(row.thr, 0.0)                  # bank row, no THR -> real 0

    async def test_classifier_down_fails_job(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files = [("x.pdf", b"a")]
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents",
                               _async_raise(UpstreamUnreachableError("classifier down"))):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("classifier", job.error)

    async def test_extractor_down_degrades_not_fails(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files = [("slip.pdf", b"a"), ("mut.pdf", b"b")]
        classify = _async([
            {"filename": "slip.pdf", "document_type": "slip", "confidence": "high"},
            {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        slips = _async([{"source_file": "slip.pdf", "worker_name": "SITI",
                         "total_paid": 6_000_000.0, "period": "2025-02"}])
        sk = _async({"summary": {}})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations",
                               _async_raise(UpstreamUnreachableError("mutasi down"))), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.income.basis, "slip_fallback")
        self.assertTrue(job.result.audit.extractor_errors)

    async def test_unexpected_internal_error_fails_job(self):
        files = [("mut.pdf", b"b")]
        classify = _async([
            {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        mutasi = _async({"files": [], "credits": [], "audit": {}})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline, "compute_income",
                               side_effect=RuntimeError("boom")):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("internal error", job.error)

    async def _bank_verified_setup(self):
        from ocr_orchestrator.models import CollateralInput, LoanRequest
        files = [("slip_mar.pdf", b"a"), ("mut.pdf", b"b")]
        classify = _async([
            {"filename": "slip_mar.pdf", "document_type": "slip", "confidence": "high"},
            {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
        ])
        mutasi = _async({
            "files": [{"filename": "mut.pdf", "account": {"nama": "BUDI"}}],
            "credits": [{"source_file": "mut.pdf", "tanggal": "2025-03-25",
                         "keterangan": "GAJI", "amount": 20_000_000.0, "page": 1,
                         "category": "Gaji"}],
            "audit": {},
        })
        slips = _async([{"source_file": "slip_mar.pdf", "worker_name": "BUDI",
                         "total_paid": 20_000_000.0, "period": "2025-03"}])
        sk = _async({"summary": {}})
        collateral = CollateralInput(luas_tanah=80.0, luas_bangunan=50.0)
        loan = LoanRequest(loan_amount=700_000_000, tenor_months=240,
                           annual_interest_rate=0.10)
        return files, classify, mutasi, slips, sk, collateral, loan

    async def test_fmv_and_decide_run_when_inputs_present(self):
        files, classify, mutasi, slips, sk, collateral, loan = \
            await self._bank_verified_setup()
        fmv = _async({"land_value": 600_000_000, "building_value": 400_000_000,
                      "fair_value": 1_000_000_000, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.fmv.fair_value, 1_000_000_000)
        self.assertEqual(job.result.decision.recommendation, "eligible")
        self.assertTrue(job.result.decision.ltv.passed)
        fmv_stage = next(s for s in job.stages if s.name == "fmv")
        decide_stage = next(s for s in job.stages if s.name == "decide")
        self.assertEqual(fmv_stage.status, "completed")
        self.assertEqual(decide_stage.status, "completed")

    async def test_stages_skipped_when_no_collateral_or_loan(self):
        files, classify, mutasi, slips, sk, _c, _l = await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.result.fmv)
        self.assertIsNone(job.result.decision)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "skipped")
        self.assertEqual(next(s for s in job.stages if s.name == "decide").status, "skipped")

    async def test_fmv_down_degrades_to_refer(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        files, classify, mutasi, slips, sk, collateral, loan = \
            await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk), \
             mock.patch.object(pipeline.upstream, "predict_fair_value",
                               _async_raise(UpstreamUnreachableError("fmv down"))):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertIsNone(job.result.fmv)
        self.assertEqual(job.result.decision.recommendation, "refer_to_analyst")
        self.assertTrue(job.result.audit.fmv_errors)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "failed")

    async def test_input_warnings_land_in_audit(self):
        files, classify, mutasi, slips, sk, _c, _l = await self._bank_verified_setup()
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", classify), \
             mock.patch.object(pipeline.upstream, "parse_slips", slips), \
             mock.patch.object(pipeline.upstream, "extract_mutations", mutasi), \
             mock.patch.object(pipeline.upstream, "parse_sk", sk):
            await pipeline.run_job(store, job.id, files, bonus_accept_pct=0.0,
                                   password=None, input_warnings=["partial loan ignored"])
        self.assertIn("partial loan ignored", job.result.audit.warnings)


if __name__ == "__main__":
    unittest.main()
