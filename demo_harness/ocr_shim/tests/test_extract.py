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


def test_page_texts_pypdfium_reads_text_layer(make_text_pdf):
    pdf = make_text_pdf(["Hello OCR shim", "Second page words"])
    texts = E.page_texts_pypdfium(pdf)
    assert len(texts) == 2
    assert "Hello OCR shim" in texts[0]
    assert "Second page words" in texts[1]


def test_extract_markdown_end_to_end_text_layer(make_text_pdf):
    pdf = make_text_pdf(["Gaji pokok 5000000"])
    md, warnings = E.extract_markdown(pdf, enable_tesseract=False, min_chars=10)
    assert "Gaji pokok 5000000" in md
    assert warnings == []


def test_blank_pdf_disabled_tesseract_warns(make_blank_pdf):
    pdf = make_blank_pdf(1)
    md, warnings = E.extract_markdown(pdf, enable_tesseract=False, min_chars=10)
    assert md == ""
    assert warnings == ["page 1: no text layer; Tesseract disabled"]


def test_tesseract_ocr_page_exists_and_is_callable():
    assert callable(E.tesseract_ocr_page)
