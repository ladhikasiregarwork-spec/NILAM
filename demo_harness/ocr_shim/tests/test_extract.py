from demo_harness.ocr_shim import extract as E


def test_assemble_markdown_joins_nonempty_pages():
    assert E.assemble_markdown(["a", "", "b"]) == "a\n\nb"


def test_extract_from_texts_keeps_pages_above_threshold():
    md, warnings = E.extract_from_texts(["plenty of text here", "tiny"], min_chars=10,
                                        enable_tesseract=False, ocr_page=None)
    assert "plenty of text here" in md
    assert warnings == ["page 2: no text layer; Tesseract disabled"]


def test_extract_from_texts_uses_injected_ocr_when_enabled():
    calls = []
    def fake_ocr(index):
        calls.append(index)
        return "OCR RECOVERED"
    md, warnings = E.extract_from_texts(["", "good long text here"], min_chars=10,
                                        enable_tesseract=True, ocr_page=fake_ocr)
    assert calls == [0]
    assert "OCR RECOVERED" in md
    assert warnings == ["page 1: used Tesseract OCR"]
