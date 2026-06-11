import unittest
from unittest import mock

from ocr_match import upstream


class _FakeResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, files=None, data=None, params=None):
        return self._resp


def _patch_client(resp):
    return mock.patch.object(upstream.httpx, "AsyncClient",
                             lambda *a, **k: _FakeClient(resp))


class TestPassthrough(unittest.IsolatedAsyncioTestCase):
    async def test_parse_slips_returns_typed_and_raw(self):
        body = {"documents": [{"source_file": "s.pdf", "total_paid": 1.0}]}
        with _patch_client(_FakeResp(200, body)):
            slips, raw = await upstream.parse_slips([("s.pdf", b"x")])
        self.assertEqual(len(slips), 1)
        self.assertEqual(slips[0].source_file, "s.pdf")
        self.assertEqual(raw, body)

    async def test_extract_mutations_filters_typed_but_keeps_all_in_raw(self):
        body = {
            "files": [{"filename": "m.pdf", "account": {"nama": "BUDI"}}],
            "credits": [
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "GAJI",
                 "amount": 9.0, "page": 1, "category": "Gaji"},
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "THR",
                 "amount": 5.0, "page": 1, "category": "THR"},
            ],
            "audit": {},
        }
        with _patch_client(_FakeResp(200, body)):
            credits, raw = await upstream.extract_mutations([("m.pdf", b"x")])
        # typed list is Gaji-only (used by the matcher)...
        self.assertEqual([c.category for c in credits], ["Gaji"])
        # ...but the raw passthrough keeps every category.
        self.assertEqual([c["category"] for c in raw["credits"]], ["Gaji", "THR"])


if __name__ == "__main__":
    unittest.main()
