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
