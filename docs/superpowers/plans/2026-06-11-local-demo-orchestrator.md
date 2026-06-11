# Local Demo Harness for `ocr_orchestrator` — Implementation Plan

> **Status — 2026-06-11: ✅ Implemented & shipped to `main` (tests passing).** The step checkboxes below are the original execution checklist, kept for history and not individually re-ticked (a few `(Optional)` manual/networked steps were not run).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run `ocr_orchestrator` end-to-end for real, fully offline on a CPU-only machine, by adding two local stand-ins (an OCR shim and an LLM adapter) and editing only `.env` — no changes to the five NILAM service packages.

**Architecture:** Two new standalone FastAPI apps under `demo_harness/`. The **OCR shim** reproduces the corporate PaddleOCR `/predict/markdown` contract on `:8060`, extracting text with pypdfium2 (plus an optional, gated Tesseract fallback for scanned pages). The **LLM adapter** serves Azure OpenAI's `POST /openai/deployments/{deployment}/chat/completions` route on `:4000`, forwarding to a local Ollama OpenAI-compatible endpoint. The five services are pointed at these via `.env` only. Neither app imports the service packages.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pypdfium2, httpx; Ollama (model runtime); pytest + respx + reportlab (tests); pytesseract + Pillow (optional Tesseract). Source spec: `docs/superpowers/specs/2026-06-11-local-demo-orchestrator-design.md`.

> **Commit policy (read first):** The workspace is being kept **local/uncommitted** for now (`docs/` and `CLAUDE.md` are gitignored; the user declined committing the spec). `demo_harness/` is **not** gitignored, so you *may* commit it later if desired. This plan uses **checkpoint** steps (run the test suite) in place of commit steps. If you decide to track `demo_harness/`, commit at each checkpoint with the suggested message. Do not commit `docs/`, `.env`, or `CLAUDE.md`.

---

## File Structure

```
demo_harness/
├── __init__.py
├── requirements.txt              # extra deps for the harness (installed into the shared .venv)
├── README.md                     # how to run the offline demo
├── conftest.py                   # pytest fixtures (make_text_pdf, make_blank_pdf)
├── ocr_shim/
│   ├── __init__.py
│   ├── config.py                 # OCR_SHIM_* settings (tesseract flag, min-chars threshold)
│   ├── extract.py                # pure extraction + pypdfium2 + gated tesseract
│   ├── app.py                    # FastAPI: POST /predict/markdown, GET /health
│   └── tests/
│       ├── __init__.py
│       ├── test_extract.py
│       └── test_app.py
├── llm_adapter/
│   ├── __init__.py
│   ├── config.py                 # OLLAMA_URL, model map, default model, timeout
│   ├── translate.py              # pure request/response mapping
│   ├── app.py                    # FastAPI: POST /openai/deployments/{deployment}/chat/completions, GET /health
│   ├── litellm.config.yaml       # OPTIONAL alternative adapter (documented, not wired by default)
│   └── tests/
│       ├── __init__.py
│       ├── test_translate.py
│       └── test_app.py
└── scripts/
    ├── start_demo.ps1            # launch every process in dependency order
    └── check_health.ps1          # curl all /health endpoints + the two contract probes
```

`.env` (repo root, gitignored) is edited by hand per Task 9 — never created by code.

---

## Task 1: Scaffold `demo_harness/` and install deps

**Files:**
- Create: `demo_harness/__init__.py` (empty)
- Create: `demo_harness/ocr_shim/__init__.py` (empty)
- Create: `demo_harness/ocr_shim/tests/__init__.py` (empty)
- Create: `demo_harness/llm_adapter/__init__.py` (empty)
- Create: `demo_harness/llm_adapter/tests/__init__.py` (empty)
- Create: `demo_harness/requirements.txt`
- Create: `demo_harness/conftest.py`

- [ ] **Step 1: Create the package `__init__.py` files**

Create all five `__init__.py` files listed above as empty files.

- [ ] **Step 2: Write `demo_harness/requirements.txt`**

```text
# Extra deps for the local demo harness (installed into the shared repo-root .venv).
# fastapi, uvicorn, pypdfium2, httpx, python-multipart are already in the
# repo-root requirements.txt — listed here only for standalone clarity.

# Test-only
pytest>=8.0,<9
respx>=0.21,<1            # mock httpx calls to Ollama in llm_adapter tests
reportlab>=4.0,<5         # generate text-layer PDF fixtures in tests

# Optional: only needed if you enable the Tesseract fallback for scanned pages
# pytesseract>=0.3.13,<1
# Pillow>=10.0,<12
```

- [ ] **Step 3: Install into the shared venv**

Run (Windows, from repo root):
```
.venv\Scripts\python -m pip install -r demo_harness\requirements.txt
```
Expected: installs pytest, respx, reportlab (others already satisfied).

- [ ] **Step 4: Write `demo_harness/conftest.py`**

```python
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
```

- [ ] **Step 5: Checkpoint — verify fixtures import**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: `no tests ran` (0 tests collected) with **no import/collection errors**.
(If committing `demo_harness/`: `git add demo_harness && git commit -m "chore(demo): scaffold demo_harness package + test fixtures"`.)

---

## Task 2: OCR shim — pure assembly + threshold logic

**Files:**
- Create: `demo_harness/ocr_shim/extract.py`
- Test: `demo_harness/ocr_shim/tests/test_extract.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: FAIL — `module 'demo_harness.ocr_shim.extract' has no attribute 'assemble_markdown'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 3 passed.
(Optional commit: `git commit -m "feat(demo): OCR shim pure assembly + threshold logic"`.)

---

## Task 3: OCR shim — pypdfium2 page-text extraction

**Files:**
- Modify: `demo_harness/ocr_shim/extract.py` (add `page_texts_pypdfium` and `extract_markdown`)
- Test: `demo_harness/ocr_shim/tests/test_extract.py` (append)

- [ ] **Step 1: Write the failing test**

Append:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: FAIL — `extract` has no attribute `page_texts_pypdfium`.

- [ ] **Step 3: Write minimal implementation**

Add to `extract.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 5 passed.
(Optional commit: `git commit -m "feat(demo): OCR shim pypdfium2 extraction"`.)

---

## Task 4: OCR shim — gated Tesseract fallback

**Files:**
- Modify: `demo_harness/ocr_shim/extract.py` (add `tesseract_ocr_page`)
- Test: `demo_harness/ocr_shim/tests/test_extract.py` (append)

- [ ] **Step 1: Write the failing test**

Append (the test injects a fake to avoid requiring Tesseract installed, and asserts graceful degradation when it is disabled):
```python
def test_blank_pdf_disabled_tesseract_warns(make_blank_pdf):
    pdf = make_blank_pdf(1)
    md, warnings = E.extract_markdown(pdf, enable_tesseract=False, min_chars=10)
    assert md == ""
    assert warnings == ["page 1: no text layer; Tesseract disabled"]


def test_tesseract_ocr_page_exists_and_is_callable():
    # We don't run real Tesseract here (it may be absent); we only assert the
    # function exists with the (pdf_bytes, index) signature for the app to inject.
    assert callable(E.tesseract_ocr_page)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: FAIL — `extract` has no attribute `tesseract_ocr_page`.

- [ ] **Step 3: Write minimal implementation**

Add to `extract.py`:
```python
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
```

Note the signature is `(pdf_bytes, index)`; the app (Task 5) wraps it as `lambda i: tesseract_ocr_page(data, i)` to match the `ocr_page` injection point's `(index)` shape.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_extract.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 7 passed.
(Optional commit: `git commit -m "feat(demo): OCR shim gated Tesseract fallback"`.)

---

## Task 5: OCR shim — config + FastAPI app (`/predict/markdown`, `/health`)

**Files:**
- Create: `demo_harness/ocr_shim/config.py`
- Create: `demo_harness/ocr_shim/app.py`
- Test: `demo_harness/ocr_shim/tests/test_app.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from demo_harness.ocr_shim.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_predict_markdown_matches_contract(make_text_pdf):
    pdf = make_text_pdf(["Slip Gaji Pokok 5000000"])
    r = client.post(
        "/predict/markdown",
        params={"skip_orientation": "false"},
        headers={"X-API-Key": "ignored"},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["response_code"] == 200
    assert body["request_id"].startswith("local-")
    assert "Slip Gaji Pokok 5000000" in body["data"]["markdown"]


def test_predict_markdown_blank_page_is_200_with_warning(make_blank_pdf):
    r = client.post(
        "/predict/markdown",
        files={"file": ("scan.pdf", make_blank_pdf(1), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["response_code"] == 200            # NOT an error — empty is allowed
    assert body["data"]["markdown"] == ""
    assert body["warnings"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: demo_harness.ocr_shim.app`.

- [ ] **Step 3: Write `config.py`**

```python
"""OCR shim settings, read from the environment (so .env / start script can tune)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    enable_tesseract: bool
    min_chars: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        enable_tesseract=os.environ.get("OCR_SHIM_TESSERACT", "false").strip().lower() == "true",
        min_chars=int(os.environ.get("OCR_SHIM_MIN_CHARS", "10") or "10"),
    )
```

- [ ] **Step 4: Write `app.py`**

```python
"""PaddleOCR stand-in: reproduces the `/predict/markdown` contract the NILAM
services expect, backed by pypdfium2 (+ optional Tesseract). No service-package
imports — this is a pure boundary replacement configured via OCR_ENDPOINT_URL.
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
    return {
        "response_code": 200,
        "request_id": f"local-{_counter['n']}",
        "response_time_ms": int((time.perf_counter() - started) * 1000),
        "data": {"markdown": markdown},
        "warnings": warnings,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/ocr_shim/tests/test_app.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Manual contract check (optional, real server)**

Run: `.venv\Scripts\uvicorn demo_harness.ocr_shim.app:app --port 8060`
Then in another shell: `curl -s -F "file=@somefile.pdf" "http://127.0.0.1:8060/predict/markdown"`
Expected: JSON with `response_code: 200` and `data.markdown` populated.

- [ ] **Step 7: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 10 passed.
(Optional commit: `git commit -m "feat(demo): OCR shim FastAPI app + /predict/markdown contract"`.)

---

## Task 6: LLM adapter — pure request/response mapping

**Files:**
- Create: `demo_harness/llm_adapter/translate.py`
- Test: `demo_harness/llm_adapter/tests/test_translate.py`

- [ ] **Step 1: Write the failing test**

```python
from demo_harness.llm_adapter import translate as T


def test_resolve_model_uses_map_then_default():
    model_map = {"gpt-4.1-mini": "qwen2.5:7b-instruct"}
    assert T.resolve_model("gpt-4.1-mini", model_map, "fallback") == "qwen2.5:7b-instruct"
    assert T.resolve_model("unknown-deploy", model_map, "fallback") == "fallback"


def test_prepare_ollama_payload_sets_model_and_disables_stream():
    azure_body = {
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    out = T.prepare_ollama_payload(azure_body, "qwen2.5:7b-instruct")
    assert out["model"] == "qwen2.5:7b-instruct"
    assert out["stream"] is False
    assert out["response_format"] == {"type": "json_object"}   # passed through (Ollama OpenAI mode honors it)
    assert azure_body is not out                                # did not mutate caller's dict
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/llm_adapter/tests/test_translate.py -v`
Expected: FAIL — module `translate` not found.

- [ ] **Step 3: Write minimal implementation**

```python
"""Pure mapping between the Azure chat-completions request the NILAM services
send and the body Ollama's OpenAI-compatible endpoint expects. Kept pure so it
is unit-testable without a running Ollama.
"""
from __future__ import annotations

from typing import Any


def resolve_model(deployment: str, model_map: dict[str, str], default_model: str) -> str:
    """Map the Azure 'deployment' name to a local Ollama model."""
    return model_map.get(deployment, default_model)


def prepare_ollama_payload(azure_body: dict[str, Any], model: str) -> dict[str, Any]:
    """Copy the request, point it at the local model, and force non-streaming.

    Ollama's /v1/chat/completions accepts the same shape as Azure/OpenAI
    (messages, temperature, max_tokens, response_format), so this is mostly a
    model-name swap. Returns a new dict — never mutates the caller's body.
    """
    body = dict(azure_body)
    body["model"] = model
    body["stream"] = False
    return body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/llm_adapter/tests/test_translate.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 12 passed.
(Optional commit: `git commit -m "feat(demo): LLM adapter pure translate functions"`.)

---

## Task 7: LLM adapter — config + FastAPI app (Azure route, Ollama forward)

**Files:**
- Create: `demo_harness/llm_adapter/config.py`
- Create: `demo_harness/llm_adapter/app.py`
- Test: `demo_harness/llm_adapter/tests/test_app.py`

- [ ] **Step 1: Write the failing test (respx mocks Ollama)**

```python
import httpx
import respx
from httpx import Response
from fastapi.testclient import TestClient

from demo_harness.llm_adapter.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# assert_all_mocked=False lets the TestClient's own ASGI request to the app pass
# through respx; only the outbound call to Ollama is intercepted.
@respx.mock(assert_all_mocked=False)
def test_azure_route_forwards_to_ollama_and_returns_openai_shape():
    ollama = respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "{\"document_type\":\"slip\"}"}}]
        })
    )
    r = client.post(
        "/openai/deployments/gpt-4.1-mini/chat/completions",
        params={"api-version": "2025-01-01-preview"},
        headers={"api-key": "ignored"},
        json={"messages": [{"role": "user", "content": "classify"}],
              "response_format": {"type": "json_object"}},
    )
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "{\"document_type\":\"slip\"}"
    # The forwarded body carried the resolved local model, not the Azure deployment name.
    sent = ollama.calls.last.request
    assert b'"model":"qwen2.5:7b-instruct"' in sent.content.replace(b" ", b"")


@respx.mock(assert_all_mocked=False)
def test_ollama_unreachable_returns_502_error_body():
    respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("refused"))
    r = client.post(
        "/openai/deployments/gpt-4.1-mini/chat/completions",
        json={"messages": []},
    )
    assert r.status_code == 502
    assert "error" in r.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest demo_harness/llm_adapter/tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: demo_harness.llm_adapter.app`.

- [ ] **Step 3: Write `config.py`**

```python
"""LLM adapter settings. Maps the Azure deployment name the services send onto a
local Ollama model, and locates the Ollama server."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    default_model: str
    model_map: dict = field(default_factory=dict)
    timeout_s: float = 300.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_model = os.environ.get("LLM_ADAPTER_MODEL", "qwen2.5:7b-instruct").strip()
    # The services send AZURE_OPENAI_DEPLOYMENT (default 'gpt-4.1-mini') as the
    # model/deployment name; route whatever they send to the local model.
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini").strip()
    return Settings(
        ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        default_model=default_model,
        model_map={deployment: default_model},
        timeout_s=float(os.environ.get("LLM_ADAPTER_TIMEOUT_S", "300") or "300"),
    )
```

- [ ] **Step 4: Write `app.py`**

```python
"""Azure-OpenAI stand-in: serves the `/openai/deployments/{deployment}/chat/completions`
route the NILAM services build, forwarding to a local Ollama OpenAI-compatible
endpoint. Configured via AZURE_OPENAI_ENDPOINT pointing here; no code changes to
the services.
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import translate as T
from .config import get_settings

app = FastAPI(title="LLM adapter (Azure-OpenAI stand-in)")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "llm-adapter"}


@app.post("/openai/deployments/{deployment}/chat/completions")
async def chat_completions(deployment: str, request: Request) -> JSONResponse:
    settings = get_settings()
    azure_body = await request.json()
    model = T.resolve_model(deployment, settings.model_map, settings.default_model)
    payload = T.prepare_ollama_payload(azure_body, model)
    try:
        async with httpx.AsyncClient(timeout=settings.timeout_s) as client:
            resp = await client.post(f"{settings.ollama_url}/v1/chat/completions", json=payload)
    except httpx.HTTPError as exc:
        return JSONResponse(
            {"error": {"message": f"ollama unreachable: {exc}", "type": "upstream_error"}},
            status_code=502,
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest demo_harness/llm_adapter/tests/test_app.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 15 passed.
(Optional commit: `git commit -m "feat(demo): LLM adapter FastAPI app forwarding to Ollama"`.)

---

## Task 8: Document the optional LiteLLM alternative

The spec defers "LiteLLM vs. tiny shim" to implementation; the tiny shim above is the default, guaranteed-working path. This task records LiteLLM as a swap-in alternative — **no code, no tests**, just a config file + README note for whoever prefers it.

**Files:**
- Create: `demo_harness/llm_adapter/litellm.config.yaml`

- [ ] **Step 1: Write `litellm.config.yaml`**

```yaml
# OPTIONAL alternative to the tiny llm_adapter shim.
# Run with:  litellm --config demo_harness/llm_adapter/litellm.config.yaml --port 4000
# Then point AZURE_OPENAI_ENDPOINT at http://127.0.0.1:4000 exactly as for the shim.
# Validate the Azure route first (see README "One-curl Azure-route test") before
# wiring the services — if it answers the /openai/deployments/... path, use it;
# otherwise stick with the tiny shim.
model_list:
  - model_name: gpt-4.1-mini          # the AZURE_OPENAI_DEPLOYMENT the services send
    litellm_params:
      model: ollama/qwen2.5:7b-instruct
      api_base: http://127.0.0.1:11434
```

- [ ] **Step 2: Checkpoint (no tests changed)**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 15 passed.
(Optional commit: `git commit -m "docs(demo): optional LiteLLM adapter config"`.)

---

## Task 9: `.env` configuration for the five services

No code changes — this task documents the exact repo-root `.env` block that swaps the services onto the local stand-ins and bumps timeouts. All keys map to existing settings (verified against the code).

**Files:**
- Modify (by hand): `<repo-root>/.env`  (gitignored — never committed)

- [ ] **Step 1: Add/replace these keys in the repo-root `.env`**

```ini
# ---- OCR -> local shim (Task 5) ----
OCR_ENDPOINT_URL=http://127.0.0.1:8060/predict/markdown
OCR_API_KEY=local-demo
OCR_SKIP_ORIENTATION=false
OCR_TIMEOUT_S=300

# ---- LLM -> local adapter (Task 7), Azure URL shape ----
AZURE_OPENAI_ENDPOINT=http://127.0.0.1:4000
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_KEY=local-demo
AZURE_OPENAI_API_VERSION=2025-01-01-preview
LLM_REQUEST_TIMEOUT_S=300

# ---- Orchestrator upstream registry: MUST be the renumbered 5001-5004 ports ----
OCR_CLASSIFIER_URL=http://127.0.0.1:5001
OCR_SK_URL=http://127.0.0.1:5002
OCR_SLIP_URL=http://127.0.0.1:5003
OCR_MUTASI_URL=http://127.0.0.1:5004
UPSTREAM_TIMEOUT_S=300

# ---- Optional: enable scanned-page OCR in the shim (needs pytesseract+Pillow) ----
# OCR_SHIM_TESSERACT=true
```

- [ ] **Step 2: Verify the orchestrator reads the right ports/timeout**

Run from repo root:
```
.venv\Scripts\python -c "from ocr_orchestrator.config import get_settings; s=get_settings(); print(s.ocr_classifier_url, s.ocr_mutasi_url, s.upstream_timeout_s)"
```
Expected: `http://127.0.0.1:5001 http://127.0.0.1:5004 300.0`
(If it prints `...:8000 ...:8300 180.0`, the `.env` keys are missing — `ocr_orchestrator/config.py` has stale 8000–8300 defaults; fix the `.env`.)

- [ ] **Step 3: Known limitation to record (no action)**

`ocr_slip`'s LLM text fallback (`ocr_slip/extract_llm.py`) hard-codes a 60s timeout, independent of `LLM_REQUEST_TIMEOUT_S`. On CPU a slow slip-LLM call could time out. Mitigation (no code change): demo with text-layer slips (which parse via pypdfium2 and skip the LLM), or keep slip bundles small. Documented in the README.

---

## Task 10: Startup + health-check PowerShell scripts

**Files:**
- Create: `demo_harness/scripts/start_demo.ps1`
- Create: `demo_harness/scripts/check_health.ps1`

- [ ] **Step 1: Write `start_demo.ps1`**

```powershell
# Launch the full offline demo stack in dependency order.
# Run from the repo root:  .\demo_harness\scripts\start_demo.ps1
# Prereqs: Ollama installed + model pulled (see README), shared .venv ready.

$ErrorActionPreference = "Stop"
$venv = ".\.venv\Scripts"

function Start-Svc($title, $cmd) {
    Write-Host "Starting $title ..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd | Out-Null
    Start-Sleep -Seconds 2
}

# 1. Ollama (model runtime). Skip if already running as a service.
Start-Svc "ollama"        "ollama serve"
# 2. LLM adapter (Azure stand-in)  :4000
Start-Svc "llm-adapter"   "$venv\uvicorn demo_harness.llm_adapter.app:app --port 4000"
# 3. OCR shim (PaddleOCR stand-in) :8060
Start-Svc "ocr-shim"      "$venv\uvicorn demo_harness.ocr_shim.app:app --port 8060"
# 4. The five NILAM services (renumbered ports)
Start-Svc "ocr_classifier" "$venv\uvicorn ocr_classifier.api:app --port 5001"
Start-Svc "ocr_sk"         "$venv\uvicorn ocr_sk.app:app --port 5002"
Start-Svc "ocr_slip"       "$venv\uvicorn ocr_slip.app:app --port 5003"
Start-Svc "ocr_mutasi"     "$venv\uvicorn ocr_mutasi.api:app --port 5004"
# 5. Orchestrator :8500
Start-Svc "ocr_orchestrator" "$venv\uvicorn ocr_orchestrator.api:app --port 8500"

Write-Host ""
Write-Host "All processes launched. Wait ~10s, then run: .\demo_harness\scripts\check_health.ps1"
Write-Host "Pre-warm the model once:  ollama run qwen2.5:7b-instruct `"ok`""
```

- [ ] **Step 2: Write `check_health.ps1`**

```powershell
# Probe every health endpoint + the two contract endpoints.
# Run from repo root:  .\demo_harness\scripts\check_health.ps1

$targets = @{
    "ocr-shim       :8060" = "http://127.0.0.1:8060/health"
    "llm-adapter    :4000" = "http://127.0.0.1:4000/health"
    "ocr_classifier :5001" = "http://127.0.0.1:5001/health"
    "ocr_sk         :5002" = "http://127.0.0.1:5002/health"
    "ocr_slip       :5003" = "http://127.0.0.1:5003/health"
    "ocr_mutasi     :5004" = "http://127.0.0.1:5004/health"
    "orchestrator   :8500" = "http://127.0.0.1:8500/health"
}
foreach ($name in $targets.Keys) {
    try {
        $r = Invoke-RestMethod -Uri $targets[$name] -TimeoutSec 5
        Write-Host ("OK   {0}  ->  {1}" -f $name, ($r | ConvertTo-Json -Compress))
    } catch {
        Write-Host ("DOWN {0}  ->  {1}" -f $name, $_.Exception.Message) -ForegroundColor Red
    }
}
```

- [ ] **Step 3: Manual validation**

Run: `.\demo_harness\scripts\start_demo.ps1` then (after ~10s) `.\demo_harness\scripts\check_health.ps1`
Expected: every line prints `OK`. Investigate any `DOWN` before proceeding.

- [ ] **Step 4: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 15 passed (scripts add no tests).
(Optional commit: `git commit -m "feat(demo): start + health-check scripts"`.)

---

## Task 11: `demo_harness/README.md` (run instructions)

**Files:**
- Create: `demo_harness/README.md`

- [ ] **Step 1: Write the README**

````markdown
# Local demo harness for `ocr_orchestrator` (fully offline, CPU-only)

Runs the real orchestrator + four NILAM services end-to-end with **no internet
and no corporate network**, by swapping the two external dependencies for local
stand-ins (config-only; no service code changes):

- **OCR shim** (`:8060`) → replaces the corporate PaddleOCR `/predict/markdown`.
- **LLM adapter** (`:4000`) → replaces Azure OpenAI, backed by local **Ollama**.

See the design spec: `docs/superpowers/specs/2026-06-11-local-demo-orchestrator-design.md`.

## One-time setup (needs internet once)

1. **Python deps** (into the shared repo-root `.venv`):
   ```
   .venv\Scripts\python -m pip install -r requirements.txt
   .venv\Scripts\python -m pip install -r demo_harness\requirements.txt
   ```
2. **Ollama**: install from https://ollama.com, then pull a CPU-friendly model:
   ```
   ollama pull qwen2.5:7b-instruct
   ```
   (Drop to `qwen2.5:3b-instruct` if 7B is too slow on your CPU; set
   `LLM_ADAPTER_MODEL` to match.)
3. **`.env`**: apply the block from the plan's Task 9 to the repo-root `.env`.
4. *(Optional, scanned docs only)* install Tesseract + the deps:
   ```
   .venv\Scripts\python -m pip install pytesseract Pillow
   ```
   Install the Tesseract binary (with `ind` language data) and set
   `OCR_SHIM_TESSERACT=true`.

## Run

```
.\demo_harness\scripts\start_demo.ps1        # launches all processes
ollama run qwen2.5:7b-instruct "ok"          # pre-warm once (first call is slowest)
.\demo_harness\scripts\check_health.ps1      # all lines should say OK
```

## Validate the contracts before a real run

- OCR shim: `curl -s -F "file=@sample.pdf" http://127.0.0.1:8060/predict/markdown`
  → `response_code: 200`, `data.markdown` populated.
- LLM adapter (the exact Azure route the services use):
  ```
  curl -s -X POST "http://127.0.0.1:4000/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2025-01-01-preview" ^
    -H "api-key: local-demo" -H "Content-Type: application/json" ^
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"return {\\\"ok\\\":true} as JSON\"}],\"response_format\":{\"type\":\"json_object\"}}"
  ```
  → `choices[0].message.content` is valid JSON.

## Demo (end-to-end)

Open the orchestrator upload page: http://127.0.0.1:8500/upload — submit a small
bundle (e.g. 1 KTP + 1 slip + 1 mutasi). Expect a completed job with a non-empty
`income` and a sane `applicant.name`. CPU inference is slow (tens of seconds per
LLM call) — treat it as a scripted demo and keep bundles small.

## Notes / limitations

- `ocr_match` (`:5005`) is **not** run — the orchestrator imports its matcher.
- `ocr_slip`'s LLM fallback hard-codes a 60s timeout; prefer text-layer slips so
  it parses via pypdfium2 and skips the LLM.
- In-memory job store: single uvicorn worker; jobs are lost on restart.
````

- [ ] **Step 2: Checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 15 passed.
(Optional commit: `git commit -m "docs(demo): harness README"`.)

---

## Task 12: End-to-end validation (manual smoke)

**Files:** none (verification only).

- [ ] **Step 1: Start the stack and confirm health**

Run `start_demo.ps1`, pre-warm Ollama, run `check_health.ps1`. Expected: all `OK`.

- [ ] **Step 2: Probe both contracts**

Run the two curl probes from the README. Expected: OCR shim returns populated
`data.markdown`; LLM adapter returns valid JSON in `choices[0].message.content`.

- [ ] **Step 3: Drive the orchestrator end-to-end**

Option A — UI: submit a small bundle at http://127.0.0.1:8500/upload and poll the
returned `status_url` until `completed`.
Option B — script: run the bundled smoke script:
```
.venv\Scripts\python ocr_orchestrator\smoke_orchestrator.py
```
Expected: a `completed` job whose `result.income` is non-empty and
`result.applicant.name` is populated; `audit.stage_timings_ms` shows all five
stages ran.

- [ ] **Step 4: Confirm the OCR/LLM were actually exercised**

Check the orchestrator result `audit` / document entries reference OCR text and
LLM classifications (document types are not all `unknown`). If every document is
`unknown`, the OCR shim isn't returning text — re-check Task 5 / `OCR_ENDPOINT_URL`.

- [ ] **Step 5: Final checkpoint**

Run: `.venv\Scripts\python -m pytest demo_harness -q`
Expected: 15 passed. Demo harness complete.

---

## Self-review notes (coverage vs. spec)

- OCR shim contract (both clients, `data.markdown`, `X-API-Key`/`skip_orientation` accepted, per-page tolerance, `/health`): Tasks 2–5.
- pypdfium2 + gated/graceful Tesseract: Tasks 3–4.
- LLM adapter Azure route + Ollama forward + JSON mode pass-through + error degradation + `/health`: Tasks 6–7; LiteLLM alternative: Task 8.
- `.env`-only service config + timeout bumps + stale-default watch-out + slip-timeout limitation: Task 9.
- Startup/health scripts: Task 10. README/run + one-curl Azure test: Task 11.
- End-to-end validation via orchestrator `/upload` + `smoke_orchestrator.py`: Task 12.
- Out of scope (KTP/KK extraction, FMV, frontend): not planned, per spec.
