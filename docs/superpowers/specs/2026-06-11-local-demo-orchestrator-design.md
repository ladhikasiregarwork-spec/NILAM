# Fully-local demo harness for `ocr_orchestrator`

**Date:** 2026-06-11
**Status:** ✅ Implemented (shipped to `main`, 2026-06-11)
**Scope owner:** local demo only — production wiring unchanged

## Goal

Run `ocr_orchestrator` end-to-end **for real** (genuine OCR + LLM parsing, not
mocks) on a **single offline, CPU-only machine**, with **no changes to the five
NILAM service packages' Python code**. The only external dependencies the
services need — the corporate PaddleOCR service and Azure OpenAI — are replaced
by two local stand-ins that reproduce the exact network contracts the services
expect, so the swap is configuration-only (`.env`).

This is explicitly a demo/eval harness. It does **not** change production
behavior, add features, or wire the frontend.

## Constraints (from brainstorming)

- **Offline:** no internet and no corporate network at demo time. (Model weights
  are pulled once over the internet, then it runs fully offline.)
- **No access** to the corporate PaddleOCR at `http://10.213.128.42:8060`.
- **LLM:** local only (Ollama / LM Studio class), no cloud key.
- **Hardware:** CPU only, modest laptop. Small model (3–8B), slow inference
  (tens of seconds per call) is expected and acceptable for a scripted demo.
- **Documents:** mix / unknown — design must tolerate scanned (no text layer)
  pages, not only digital PDFs.

## Why config-only works (verified against the code)

Two facts in the existing code make this a boundary swap rather than a fork:

1. **One OCR contract, two clients, both fall back to `data.markdown`.**
   - `ocr_classifier/ocr_client.py` and `ocr_common/paddle_ocr.py` both parse
     `data.json_result[*].parsing_res_list[*].block_content` and, when that is
     absent, fall back to `_strip_html(data.markdown)`.
   - Both send header `X-API-Key`, query `skip_orientation`, multipart `file`,
     and both treat `response_code != 200` or a non-empty `error_message` as a
     failure; both read `request_id` (and `response_time_ms`).
   - ⇒ A stand-in that returns
     `{"response_code":200,"request_id":"…","response_time_ms":N,"data":{"markdown":"<text>"}}`
     satisfies **both** clients. The nested `json_result` structure does **not**
     need to be reproduced.
   - Note the call pattern differs by caller: `ocr_classifier` POSTs the **whole**
     file once; `ocr_common.paddle_ocr` **splits the PDF and POSTs one page at a
     time**. The shim must handle both a multi-page and a single-page PDF and
     return that document's text either way.

2. **The LLM is reached via Azure's URL shape, which any compatible server can
   serve.**
   - SDK services (`ocr_classifier/llm_classifier.py`, `ocr_mutasi/llm_classifier.py`,
     `ocr_mutasi/ocr_fallback.py`) use `AzureOpenAI(azure_endpoint, api_key,
     api_version)` then `.chat.completions.create(model=<deployment>, …)`, which
     builds `{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=…`.
   - Hand-built-URL services (`ocr_slip/extract_llm.py`, `ocr_sk/extract_llm.py`)
     POST to that same path with header `api-key: <key>` and body containing
     `response_format: {"type":"json_object"}`, `temperature`, `max_tokens`,
     `messages`, and read `choices[0].message.content`.
   - ⇒ Anything serving `POST /openai/deployments/{deployment}/chat/completions`
     that accepts the `api-key` header and returns OpenAI-shaped
     `{choices:[{message:{content:"…"}}]}` works for all four LLM-using services.
     Pointing `AZURE_OPENAI_ENDPOINT` at it is sufficient — **no code change**.

Critical dependency: `ocr_classifier` has **no text-layer shortcut** — every
document is OCR'd then LLM-classified. The classifier is stage 1 of the
orchestrator, so a working OCR stand-in and a working LLM are both mandatory:
without OCR, every document classifies as `unknown` and the income result is
empty; the pipeline "succeeds" but is useless for a demo.

## Topology

Local processes (all `127.0.0.1`), no network after the one-time model pull —
the five NILAM services + the OCR shim + the LLM adapter (LiteLLM or shim) in
front of Ollama (the model runtime is its own process):

```
ocr_orchestrator :8500 ──┬─ ocr_classifier :5001 ─┐
                         ├─ ocr_slip      :5003 ─┤── OCR shim    :8060   (pypdfium2 [+ Tesseract])
                         ├─ ocr_mutasi    :5004 ─┤── LLM adapter :4000   (→ Ollama :11434)
                         └─ ocr_sk        :5002 ─┘
```

- `ocr_match` (:5005) is **not** run — `ocr_orchestrator` imports its matcher as
  an in-process function (`ocr_orchestrator/verify.py` → `ocr_match.matcher`).
- The five NILAM services run from the repo root on the renumbered ports
  (5001–5004; orchestrator 8500) per the root README.

## Component 1 — OCR shim (PaddleOCR stand-in)

A small standalone FastAPI app (new code, lives outside the five service
packages; does not import them).

- **Endpoint:** `POST /predict/markdown`
- **Accepts:** header `X-API-Key` (accepted and ignored), query `skip_orientation`
  (accepted and ignored), multipart field `file` = a PDF (whole document or a
  single split page).
- **Processing, per page:**
  1. `pypdfium2` text extraction (digital pages → near-perfect text, zero OCR).
  2. If a page yields effectively no text → optional **Tesseract** image OCR on
     the rendered page.
  3. Join page texts with blank lines.
- **Tesseract is behind a flag and degrades gracefully:** if disabled or not
  installed, a text-less page returns empty text plus a warning rather than
  erroring. ⇒ Works out-of-the-box for text-layer PDFs; Tesseract is installed
  only if a real demo file proves to be scanned. (Resolves the deferred
  "shim OCR depth" decision: build the Tesseract branch, ship it switchable.)
- **Returns:**
  `{"response_code":200,"request_id":"local-<n>","response_time_ms":<int>,"data":{"markdown":"<joined text>"}}`
- **Error semantics:** never 500 on a bad/blank page — empty text + warning,
  mirroring the real client's per-page tolerance. Reserve non-200 `response_code`
  for genuinely unreadable input, so the services' error paths still exercise.
- **Also expose** `GET /health`.

## Component 2 — LLM adapter (Azure-OpenAI stand-in)

Presents the Azure route on `:4000`, backed by local Ollama (`:11434`).
**Decision deferred to implementation:** pick whichever stands up more simply
after a one-curl Azure-route test. Both options are drop-in for the same `.env`.

- **Option A — LiteLLM proxy:** config maps deployment name `gpt-4.1-mini` →
  `ollama/<model>`; forwards `response_format:{type:json_object}` to Ollama JSON
  mode; gives retries/streaming/model-swap for free. Cost: one heavier pip
  dependency + a small config file.
- **Option B — tiny custom shim (~40 lines FastAPI):** implements
  `POST /openai/deployments/{deployment}/chat/completions`, forwards to Ollama
  (`/api/chat` or `/v1/chat/completions`), maps `response_format` → `format:json`,
  returns OpenAI-shaped JSON. Symmetric with the OCR shim, no heavy deps, fully
  owned. Cost: we maintain it.
- **Model:** on CPU, `qwen2.5:7b-instruct` (strong JSON + Indonesian) or
  `llama3.1:8b`; fall back to a 3B if 7B is too slow. JSON mode is important
  because all four services request strict JSON.

## Configuration (the only edits — all in repo-root `.env`)

```ini
# OCR → local shim
OCR_ENDPOINT_URL=http://127.0.0.1:8060/predict/markdown
OCR_API_KEY=local-demo            # shim ignores it
OCR_TIMEOUT_S=300                 # bumped for CPU

# LLM → local adapter (LiteLLM or shim), Azure URL shape
AZURE_OPENAI_ENDPOINT=http://127.0.0.1:4000
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini   # adapter routes this name to Ollama
AZURE_OPENAI_API_KEY=local-demo
AZURE_OPENAI_API_VERSION=2025-01-01-preview
LLM_REQUEST_TIMEOUT_S=300         # bumped for CPU

# Service registry — MUST be the renumbered ports
OCR_CLASSIFIER_URL=http://127.0.0.1:5001
OCR_SK_URL=http://127.0.0.1:5002
OCR_SLIP_URL=http://127.0.0.1:5003
OCR_MUTASI_URL=http://127.0.0.1:5004
```

⚠️ **Watch-out:** `ocr_orchestrator/config.py` still hard-codes *stale* default
upstream ports (8000/8100/8200/8300). They are only correct if `.env` supplies
`OCR_*_URL` (which pydantic-settings maps onto the `ocr_*_url` fields). Ensure
those four keys are present, or the orchestrator will call the wrong ports.

## CPU realities (designed-in, not afterthoughts)

- **Timeouts bumped** at three layers: `OCR_TIMEOUT_S`, `LLM_REQUEST_TIMEOUT_S`,
  and the orchestrator's `upstream_timeout_s` (default 180 → 300+). A CPU bundle
  can take minutes; the mutasi batch LLM parse is the slowest leg.
- **Pre-warm Ollama** (one throwaway call) before demoing.
- Treat as a **scripted** demo; keep bundles small (e.g. 1 slip + 1 mutasi +
  1 KTP) to bound the LLM call count.

## Data flow (one bundle)

1. Orchestrator `classify`: each file → `ocr_classifier` → OCR shim (text) →
   local LLM (label). Slips/mutasi/sk/ktp/kk identified.
2. `extract` (concurrent): slips → `ocr_slip`, mutasi → `ocr_mutasi`, sk →
   `ocr_sk`. Text-layer docs parse via pypdfium2 (no shim call); weak/scanned
   pages fall back to the OCR shim. LLM used where each service uses it.
3. `verify`: in-process `ocr_match` matcher pairs slips ↔ bank `Gaji` credits.
4. `aggregate`: monthly qualifying income via `ocr_orchestrator/income.py`.
5. `assemble`: applicant name (slip → mutasi → sk), audit, timings.

## Error handling

- OCR shim: per-page tolerance, no 500s on blank pages; `/health`.
- LLM adapter: surface upstream Ollama errors as OpenAI-shaped error bodies so the
  services' existing `audit`-block degradation still triggers (errors land in
  responses, not as 500s).
- Orchestrator already fails the job cleanly on a classifier outage and degrades
  on extractor outages — unchanged.

## Validation / testing

- **Contracts first (before touching services):**
  - `curl -F file=@sample.pdf http://127.0.0.1:8060/predict/markdown` → 200 with
    `data.markdown` populated.
  - One **Azure-shaped** curl to the LLM adapter
    (`POST /openai/deployments/gpt-4.1-mini/chat/completions`, header `api-key`,
    body with `response_format:{type:json_object}`) → `choices[0].message.content`
    is valid JSON.
- `/health` on the shim, the LLM adapter, and all five services.
- **End-to-end:** drive `ocr_orchestrator`'s `/upload` page (or
  `ocr_orchestrator/smoke_orchestrator.py`) with a real bundle; assert a
  non-empty `income` and a sane `applicant.name`.
- **Startup script:** a PowerShell script that launches every process in
  dependency order (Ollama → LLM adapter → OCR shim → five NILAM services →
  orchestrator) and prints health status.

## Out of scope

KTP/KK field extraction, FMV (`house_fair_market_value`), the approve/reject
decision, and any frontend wiring. Single-applicant v1, matching the
orchestrator's own stated scope. No production behavior changes — the harness is
additive (two new local apps + `.env`).

## Open decisions for implementation

1. **LLM adapter:** LiteLLM vs. tiny shim — choose after the one-curl Azure-route
   test (whichever is simpler to stand up). Design both as `.env`-compatible.
2. **Local model:** confirm `qwen2.5:7b-instruct` is acceptable on the target CPU;
   fall back to 3B if too slow.
3. **Tesseract:** install only if a demo file is confirmed scanned (Indonesian
   `ind` traineddata if so).
