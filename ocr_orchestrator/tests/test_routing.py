import unittest

from ocr_orchestrator.routing import route_documents


def _cls(filename, doc_type, conf="high"):
    return {"filename": filename, "document_type": doc_type, "confidence": conf}


class TestRouteDocuments(unittest.TestCase):
    def setUp(self):
        self.files = [
            ("slip1.pdf", b"a"), ("mut1.pdf", b"b"), ("sk1.pdf", b"c"),
            ("ktp1.pdf", b"d"), ("kk1.pdf", b"e"), ("weird.pdf", b"f"),
        ]
        self.classifications = [
            _cls("slip1.pdf", "slip"), _cls("mut1.pdf", "mutasi"),
            _cls("sk1.pdf", "sk"), _cls("ktp1.pdf", "ktp"),
            _cls("kk1.pdf", "kk"), _cls("weird.pdf", "unknown"),
        ]

    def test_buckets_by_type(self):
        buckets, docs, warnings = route_documents(self.classifications, self.files)
        self.assertEqual([n for n, _ in buckets.slips], ["slip1.pdf"])
        self.assertEqual([n for n, _ in buckets.mutasi], ["mut1.pdf"])
        self.assertEqual([n for n, _ in buckets.sk], ["sk1.pdf"])

    def test_document_status_mapping(self):
        _, docs, _ = route_documents(self.classifications, self.files)
        status = {d.filename: d.status for d in docs}
        self.assertEqual(status["slip1.pdf"], "extracted")
        self.assertEqual(status["ktp1.pdf"], "recognized_not_extracted")
        self.assertEqual(status["kk1.pdf"], "recognized_not_extracted")
        self.assertEqual(status["weird.pdf"], "unclassified")

    def test_unknown_emits_warning(self):
        _, _, warnings = route_documents(self.classifications, self.files)
        self.assertTrue(any("weird.pdf" in w for w in warnings))

    def test_one_doc_per_uploaded_file(self):
        _, docs, _ = route_documents(self.classifications, self.files)
        self.assertEqual(len(docs), len(self.files))


if __name__ == "__main__":
    unittest.main()
