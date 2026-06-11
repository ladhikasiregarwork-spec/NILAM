import unittest
from unittest import mock

from ocr_match import pipeline
from ocr_match.models import GajiCredit, ParsedSlip


class _FakeMatchSettings:
    match_amount_tolerance_rp = 1.0


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestPipelinePassthrough(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p = mock.patch("ocr_match.matcher.get_settings",
                       return_value=_FakeMatchSettings())
        self.addCleanup(p.stop)
        p.start()

    async def test_response_carries_full_extractions(self):
        slip_raw = {"documents": [{"source_file": "slip_feb.pdf",
                                   "total_paid": 9_500_000.0, "period": "2025-02"}]}
        mut_raw = {
            "files": [{"filename": "m.pdf", "account": {"nama": "BUDI"}}],
            "credits": [
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "GAJI",
                 "amount": 9_500_000.0, "page": 1, "category": "Gaji"},
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "THR",
                 "amount": 5_000_000.0, "page": 1, "category": "THR"},
            ],
            "audit": {},
        }
        slips = [ParsedSlip(**d) for d in slip_raw["documents"]]
        gaji = [GajiCredit(**c) for c in mut_raw["credits"] if c["category"] == "Gaji"]

        with mock.patch.object(pipeline, "parse_slips", _async((slips, slip_raw))), \
             mock.patch.object(pipeline, "extract_mutations", _async((gaji, mut_raw))):
            resp = await pipeline.run([("slip_feb.pdf", b"a")], [("m.pdf", b"b")])

        self.assertEqual(resp.slip_extraction, slip_raw)
        self.assertEqual([c["category"] for c in resp.mutasi_extraction["credits"]],
                         ["Gaji", "THR"])
        self.assertEqual(len(resp.matches), 1)


if __name__ == "__main__":
    unittest.main()
