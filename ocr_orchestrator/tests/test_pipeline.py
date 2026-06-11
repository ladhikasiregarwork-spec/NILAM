import unittest
from unittest import mock

from ocr_orchestrator import pipeline
from ocr_orchestrator.jobs import JobStore


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


def _async_raise(exc):
    async def _fn(*args, **kwargs):
        raise exc
    return _fn


def _match_payload(*, worker="BUDI", account="BUDI SANTOSO", amount=9_500_000.0,
                   tanggal="2025-03-25", period="2025-02", matched=True,
                   extra_credits=()):
    credits = [{"source_file": "mut.pdf", "tanggal": tanggal, "keterangan": "GAJI",
                "amount": amount, "page": 1, "category": "Gaji"}]
    credits.extend(extra_credits)
    payload = {
        "matches": [],
        "slip_extraction": {"documents": [
            {"source_file": "slip_feb.pdf#page-1", "worker_name": worker,
             "total_paid": amount, "period": period},
        ]},
        "mutasi_extraction": {
            "files": [{"filename": "mut.pdf", "account": {"nama": account}}],
            "credits": credits, "audit": {},
        },
    }
    if matched:
        payload["matches"] = [{
            "slip": {"source_file": "slip_feb.pdf#page-1"},
            "credit": {"month": tanggal[:7], "tanggal": tanggal, "amount": amount},
            "match_pattern": "next_month",
        }]
    return payload


def _classify():
    return _async([
        {"filename": "slip_feb.pdf", "document_type": "slip", "confidence": "high"},
        {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
    ])


_FILES = [("slip_feb.pdf", b"a"), ("mut.pdf", b"b")]


class TestRunJob(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_bank_verified(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload())):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.income.basis, "bank_verified")
        self.assertEqual(job.result.income.monthly_qualifying_income, 9_500_000)
        self.assertEqual(job.result.identity.ktp.nama, "BUDI")
        self.assertEqual(job.result.verification.verified_month_count, 1)

        slip_doc = next(d for d in job.result.documents if d.document_type == "slip")
        self.assertEqual(slip_doc.extracted["worker_name"], "BUDI")
        mut_doc = next(d for d in job.result.documents if d.document_type == "mutasi")
        self.assertEqual(mut_doc.extracted["account"]["nama"], "BUDI SANTOSO")

        row = job.result.income.monthly_breakdown[0]
        self.assertEqual(row.month, "2025-03")
        self.assertEqual(row.source, "bank_verified")
        self.assertEqual(row.total_paid, 9_500_000)

        from ocr_orchestrator.models import ApplicationView
        self.assertIsInstance(job.result, ApplicationView)
        self.assertEqual(job.result.installment.gaji_bulanan, 9_500_000)
        self.assertEqual(len(job.result.matching.salary_slip), 1)

    async def test_classifier_down_fails_job(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents",
                               _async_raise(UpstreamUnreachableError("classifier down"))):
            await pipeline.run_job(store, job.id, [("x.pdf", b"a")],
                                   bonus_accept_pct=0.0, password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("classifier", job.error)

    async def test_ocr_match_down_degrades_to_no_income(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async_raise(UpstreamUnreachableError("ocr_match down"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")        # D1: degrade, not fail
        self.assertEqual(job.result.income.basis, "none")
        self.assertTrue(job.result.audit.extractor_errors)
        acquire = next(s for s in job.stages if s.name == "acquire")
        self.assertEqual(acquire.status, "completed")

    async def test_unexpected_internal_error_fails_job(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload())), \
             mock.patch.object(pipeline, "compute_income",
                               side_effect=RuntimeError("boom")):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("internal error", job.error)

    def _collateral_loan(self):
        from ocr_orchestrator.models import CollateralInput, LoanRequest
        return (CollateralInput(luas_tanah=80.0, luas_bangunan=50.0),
                LoanRequest(loan_amount=700_000_000, tenor_months=240,
                            annual_interest_rate=0.10))

    async def test_fmv_and_decide_run_when_inputs_present(self):
        collateral, loan = self._collateral_loan()
        fmv = _async({"land_value": 600_000_000, "building_value": 400_000_000,
                      "fair_value": 1_000_000_000, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.agunan.npw, 1_000_000_000)
        self.assertEqual(job.result.decision.recommendation, "eligible")
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "completed")

    async def test_stages_skipped_when_no_collateral_or_loan(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertIsNone(job.result.agunan.npw)
        self.assertIsNone(job.result.decision)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "skipped")
        self.assertEqual(next(s for s in job.stages if s.name == "decide").status, "skipped")

    async def test_input_warnings_land_in_audit(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, input_warnings=["partial loan ignored"])
        self.assertIn("partial loan ignored", job.result.audit.warnings)

    async def test_match_outage_still_renders_agunan_and_decision(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        from ocr_orchestrator.models import AgunanInput, CollateralInput, LoanRequest
        collateral = CollateralInput(luas_tanah=80.0, luas_bangunan=50.0)
        loan = LoanRequest(loan_amount=410_000_000, tenor_months=180,
                           annual_interest_rate=0.105)
        agunan = AgunanInput(provinsi="Jawa Barat", harga_rumah=610_000_000.0)
        fmv = _async({"land_value": 3.0, "building_value": 2.0,
                      "fair_value": 610_000_000.0, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async_raise(UpstreamUnreachableError("ocr_match down"))), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan,
                                   agunan=agunan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.agunan.npw, 610_000_000.0)        # FMV still ran
        self.assertEqual(job.result.decision.recommendation, "refer_to_analyst")
        self.assertEqual(job.result.matching.rekap_per_bulan, [])     # no income data
        self.assertEqual(job.result.bank_statement.n_transaksi, 0)
        self.assertIsNone(job.result.installment.kemampuan_bayar)     # qi is None


if __name__ == "__main__":
    unittest.main()
