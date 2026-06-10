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


if __name__ == "__main__":
    unittest.main()
