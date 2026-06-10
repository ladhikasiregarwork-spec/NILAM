import unittest
from unittest import mock

import httpx

from ocr_orchestrator import upstream


class _FakeResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    """Stand-in for httpx.AsyncClient as an async context manager."""
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None):
        if self._exc:
            raise self._exc
        return self._resp


def _patch_client(resp=None, exc=None):
    return mock.patch.object(upstream.httpx, "AsyncClient",
                             lambda *a, **k: _FakeClient(resp=resp, exc=exc))


class TestPredictFairValue(unittest.IsolatedAsyncioTestCase):
    async def test_success_returns_json(self):
        resp = _FakeResp(200, {"land_value": 600.0, "building_value": 400.0,
                               "fair_value": 1000.0, "location_matched": True,
                               "backend": "linear", "warnings": []})
        with _patch_client(resp=resp):
            out = await upstream.predict_fair_value(
                {"luas_tanah": 80, "luas_bangunan": 50})
        self.assertEqual(out["fair_value"], 1000.0)

    async def test_transport_error_raises_unreachable(self):
        with _patch_client(exc=httpx.ConnectError("refused")):
            with self.assertRaises(upstream.UpstreamUnreachableError):
                await upstream.predict_fair_value({"luas_tanah": 80, "luas_bangunan": 50})

    async def test_4xx_raises_http_error(self):
        with _patch_client(resp=_FakeResp(400, text="bad request")):
            with self.assertRaises(upstream.UpstreamHttpError):
                await upstream.predict_fair_value({"luas_tanah": 80, "luas_bangunan": 50})


if __name__ == "__main__":
    unittest.main()
