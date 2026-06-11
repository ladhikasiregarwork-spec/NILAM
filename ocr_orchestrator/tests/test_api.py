import unittest
from unittest import mock

from fastapi.testclient import TestClient


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestApi(unittest.TestCase):
    def setUp(self):
        from ocr_orchestrator import api
        self.api = api
        self.client = TestClient(api.app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_root_redirects_to_upload(self):
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual(r.status_code, 307)
        self.assertEqual(r.headers["location"], "/upload")

    def test_post_requires_files(self):
        r = self.client.post("/api/v1/applications", files=[])
        self.assertIn(r.status_code, (400, 422))

    def test_get_unknown_job_404(self):
        r = self.client.get("/api/v1/applications/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_post_returns_202_and_job_is_retrievable(self):
        # Stub classify so the background task progresses without network.
        classify = _async([
            {"filename": "x.pdf", "document_type": "unknown", "confidence": "low"},
        ])
        with mock.patch.object(self.api.upstream, "classify_documents", classify):
            r = self.client.post(
                "/api/v1/applications",
                files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            )
            self.assertEqual(r.status_code, 202)
            body = r.json()
            self.assertIn("job_id", body)
            self.assertEqual(body["status_url"], f"/api/v1/applications/{body['job_id']}")
            # Job is retrievable; status is one of the valid states.
            g = self.client.get(body["status_url"])
            self.assertEqual(g.status_code, 200)
            self.assertIn(g.json()["status"],
                          {"pending", "running", "completed", "failed"})

    def test_invalid_harga_rumah_is_400(self):
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"harga_rumah": "-5"},
        )
        self.assertEqual(r.status_code, 400)

    def test_invalid_tenor_is_400(self):
        # validation fires before job creation — no upstream mock needed
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"tenor_months": "0"},
        )
        self.assertEqual(r.status_code, 400)

    def test_invalid_appraisal_month_is_400(self):
        r = self.client.post(
            "/api/v1/applications",
            files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
            data={"appraisal_month": "999"},
        )
        self.assertEqual(r.status_code, 400)

    def test_build_loan_from_price_derives_amount(self):
        from ocr_orchestrator.api import _build_loan_from_price
        warnings = []
        loan = _build_loan_from_price(610_000_000.0, 200_000_000.0, 180, 0.105, warnings)
        self.assertEqual(loan.loan_amount, 410_000_000.0)   # harga - dp
        self.assertEqual(loan.tenor_months, 180)
        self.assertEqual(warnings, [])

    def test_build_loan_from_price_partial_warns(self):
        from ocr_orchestrator.api import _build_loan_from_price
        warnings = []
        self.assertIsNone(_build_loan_from_price(610_000_000.0, None, 180, 0.105, warnings))
        self.assertTrue(warnings)

    def test_accepts_harga_dp_address_returns_202(self):
        classify = _async([
            {"filename": "x.pdf", "document_type": "unknown", "confidence": "low"},
        ])
        with mock.patch.object(self.api.upstream, "classify_documents", classify):
            r = self.client.post(
                "/api/v1/applications",
                files=[("files", ("x.pdf", b"%PDF-1.4 fake", "application/pdf"))],
                data={"luas_tanah": "96", "luas_bangunan": "45",
                      "kode_pos": "16969", "kelurahan": "Bojong Kulur",
                      "provinsi": "Jawa Barat", "kota_kab": "Bogor",
                      "harga_rumah": "610000000", "dp": "200000000",
                      "tenor_months": "180", "annual_interest_rate": "0.105"},
            )
            self.assertEqual(r.status_code, 202)


if __name__ == "__main__":
    unittest.main()
