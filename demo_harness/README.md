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
3. **`.env`** (repo root, gitignored): add/replace these keys. They swap the five
   services onto the local stand-ins and bump timeouts — **no code changes**.
   ```ini
   # OCR -> local shim
   OCR_ENDPOINT_URL=http://127.0.0.1:8060/predict/markdown
   OCR_API_KEY=local-demo
   OCR_SKIP_ORIENTATION=false
   OCR_TIMEOUT_S=300

   # LLM -> local adapter (Azure URL shape)
   AZURE_OPENAI_ENDPOINT=http://127.0.0.1:4000
   AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
   AZURE_OPENAI_API_KEY=local-demo
   AZURE_OPENAI_API_VERSION=2025-01-01-preview
   LLM_REQUEST_TIMEOUT_S=300

   # Orchestrator upstream registry — MUST be the renumbered 5001-5004 ports.
   # (ocr_orchestrator/config.py still hard-codes stale 8000-8300 defaults, so
   #  these keys are required or it will call the wrong ports.)
   OCR_CLASSIFIER_URL=http://127.0.0.1:5001
   OCR_SK_URL=http://127.0.0.1:5002
   OCR_SLIP_URL=http://127.0.0.1:5003
   OCR_MUTASI_URL=http://127.0.0.1:5004
   UPSTREAM_TIMEOUT_S=300

   # Optional: enable scanned-page OCR in the shim (needs pytesseract+Pillow)
   # OCR_SHIM_TESSERACT=true
   ```
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
