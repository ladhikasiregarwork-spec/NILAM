import unittest

from ocr_orchestrator import matching


class TestParseMatchResponse(unittest.TestCase):
    def test_full_response(self):
        payload = {
            "matches": [
                {"slip": {"source_file": "slip_feb.pdf#page-1"},
                 "credit": {"month": "2025-03", "tanggal": "2025-03-25",
                            "amount": 9_500_000.0},
                 "match_pattern": "next_month"},
            ],
            "slip_extraction": {"documents": [
                {"source_file": "slip_feb.pdf#page-1", "worker_name": "BUDI",
                 "total_paid": 9_500_000.0, "period": "2025-02"},
            ]},
            "mutasi_extraction": {
                "files": [{"filename": "m.pdf", "account": {"nama": "BUDI SANTOSO"}}],
                "credits": [
                    {"source_file": "m.pdf", "tanggal": "2025-03-25", "amount": 9_500_000.0,
                     "category": "Gaji"},
                    {"source_file": "m.pdf", "tanggal": "2025-03-25", "amount": 5_000_000.0,
                     "category": "THR"},
                ],
                "audit": {},
            },
        }
        slip_docs, credits, mut_files, matches, verified = \
            matching.parse_match_response(payload)

        self.assertEqual(len(slip_docs), 1)
        self.assertEqual(slip_docs[0]["worker_name"], "BUDI")
        self.assertEqual([c["category"] for c in credits], ["Gaji", "THR"])
        self.assertEqual(mut_files[0]["account"]["nama"], "BUDI SANTOSO")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].slip.source_file, "slip_feb.pdf#page-1")
        self.assertEqual(matches[0].credit.month, "2025-03")
        self.assertEqual(matches[0].match_pattern, "next_month")
        self.assertEqual(verified, {"2025-03"})

    def test_month_falls_back_to_tanggal(self):
        payload = {
            "matches": [
                {"slip": {"source_file": "s.pdf"},
                 "credit": {"tanggal": "2025-07-25", "amount": 1.0},
                 "match_pattern": "same_month"},
            ],
            "slip_extraction": {"documents": []},
            "mutasi_extraction": {"files": [], "credits": [], "audit": {}},
        }
        _slips, _credits, _files, matches, verified = \
            matching.parse_match_response(payload)
        self.assertEqual(matches[0].credit.month, "2025-07")
        self.assertEqual(verified, {"2025-07"})

    def test_empty_payload(self):
        slip_docs, credits, mut_files, matches, verified = \
            matching.parse_match_response({})
        self.assertEqual(slip_docs, [])
        self.assertEqual(credits, [])
        self.assertEqual(mut_files, [])
        self.assertEqual(matches, [])
        self.assertEqual(verified, set())


if __name__ == "__main__":
    unittest.main()
