"""Shared pytest fixtures for the demo harness tests."""
from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _text_pdf(pages_text: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages_text:
        y = 800
        for line in (text.splitlines() or [""]):
            c.drawString(72, y, line)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def make_text_pdf():
    """Return a builder: list[str] (one entry per page) -> PDF bytes with a real text layer."""
    return _text_pdf


@pytest.fixture
def make_blank_pdf():
    """A PDF whose pages have no text layer (simulates a scanned page)."""
    def _blank(n_pages: int = 1) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        for _ in range(n_pages):
            c.showPage()
        c.save()
        return buf.getvalue()
    return _blank
