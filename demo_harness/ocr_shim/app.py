"""PaddleOCR stand-in: reproduces the `/predict/markdown` contract the NILAM
services expect, backed by pypdfium2 (+ optional Tesseract). No service-package
imports. The NILAM clients reach it via their `OCR_ENDPOINT_URL`; the shim itself
is configured via `OCR_SHIM_TESSERACT` / `OCR_SHIM_MIN_CHARS`.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, File, UploadFile

from . import extract as E
from .config import get_settings

app = FastAPI(title="OCR shim (PaddleOCR stand-in)")
_counter = {"n": 0}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ocr-shim"}


@app.post("/predict/markdown")
async def predict_markdown(
    file: UploadFile = File(...),
    skip_orientation: str = "false",   # accepted + ignored (real service query flag)
) -> dict:
    settings = get_settings()
    data = await file.read()
    started = time.perf_counter()
    try:
        markdown, warnings = E.extract_markdown(
            data,
            enable_tesseract=settings.enable_tesseract,
            min_chars=settings.min_chars,
            ocr_page=(lambda i: E.tesseract_ocr_page(data, i)) if settings.enable_tesseract else None,
        )
    except Exception as exc:  # genuine failure -> error body the clients understand
        return {"response_code": 500, "error_message": f"extract failed: {exc}", "data": {}}

    _counter["n"] += 1
    n = _counter["n"]
    return {
        "response_code": 200,
        "request_id": f"local-{n}",
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "data": {"markdown": markdown},
        "warnings": warnings,
    }
