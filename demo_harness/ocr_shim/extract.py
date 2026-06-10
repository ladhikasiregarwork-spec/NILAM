"""Pure text-extraction logic for the OCR shim.

`extract_from_texts` is pure (the per-page OCR is injected) so the threshold and
warning logic is unit-testable without pypdfium2 or Tesseract. The pypdfium2 and
Tesseract integrations live in separate functions added in later tasks.
"""
from __future__ import annotations

from typing import Callable

DEFAULT_MIN_CHARS = 10


def assemble_markdown(page_texts: list[str]) -> str:
    """Join non-empty page texts with a blank line between pages."""
    return "\n\n".join(t for t in page_texts if t).strip()


def extract_from_texts(
    page_texts: list[str],
    *,
    min_chars: int,
    enable_tesseract: bool,
    ocr_page: Callable[[int], str] | None,
) -> tuple[str, list[str]]:
    """Given per-page pypdfium2 text, fill weak pages via injected OCR (if enabled).

    Returns (markdown, warnings). A page with >= min_chars is kept as-is. A weak
    page is OCR'd when enabled and an ocr_page callable is supplied; otherwise a
    warning records why it stayed empty.
    """
    texts = list(page_texts)
    warnings: list[str] = []
    for i, text in enumerate(texts):
        if len(text.strip()) >= min_chars:
            continue
        if enable_tesseract and ocr_page is not None:
            try:
                recovered = (ocr_page(i) or "").strip()
            except Exception as exc:  # never let one page sink the document
                warnings.append(f"page {i + 1}: Tesseract error: {exc}")
                recovered = ""
            if recovered:
                texts[i] = recovered
                warnings.append(f"page {i + 1}: used Tesseract OCR")
                continue
            warnings.append(f"page {i + 1}: no text layer; Tesseract empty")
        else:
            warnings.append(f"page {i + 1}: no text layer; Tesseract disabled")
    return assemble_markdown(texts), warnings


def page_texts_pypdfium(pdf_bytes: bytes) -> list[str]:
    """Extract the text layer of each page with pypdfium2. Scanned pages return ''."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        out: list[str] = []
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            out.append((textpage.get_text_range() or "").strip())
            textpage.close()
            page.close()
        return out
    finally:
        doc.close()


def extract_markdown(
    pdf_bytes: bytes,
    *,
    enable_tesseract: bool,
    min_chars: int = DEFAULT_MIN_CHARS,
    ocr_page: Callable[[int], str] | None = None,
) -> tuple[str, list[str]]:
    """Full extraction: pypdfium2 per-page text, then the threshold/OCR pass."""
    texts = page_texts_pypdfium(pdf_bytes)
    return extract_from_texts(
        texts, min_chars=min_chars, enable_tesseract=enable_tesseract, ocr_page=ocr_page
    )


def tesseract_ocr_page(pdf_bytes: bytes, index: int, *, dpi: int = 200, lang: str = "ind+eng") -> str:
    """Render one page to an image and OCR it with Tesseract.

    Imports pytesseract/Pillow lazily so the shim runs without them when the
    Tesseract fallback is disabled. Raises if they are missing — the caller in
    `extract_from_texts` already swallows the error into a per-page warning.
    """
    import pypdfium2 as pdfium
    import pytesseract  # type: ignore

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[index]
        pil_image = page.render(scale=dpi / 72).to_pil()
        page.close()
        return pytesseract.image_to_string(pil_image, lang=lang)
    finally:
        doc.close()
