# Probe every health endpoint + the two contract endpoints.
# Run from repo root:  .\demo_harness\scripts\check_health.ps1

$targets = @{
    "ocr-shim       :8060" = "http://127.0.0.1:8060/health"
    "llm-adapter    :4000" = "http://127.0.0.1:4000/health"
    "ocr_classifier :5001" = "http://127.0.0.1:5001/health"
    "ocr_sk         :5002" = "http://127.0.0.1:5002/health"
    "ocr_slip       :5003" = "http://127.0.0.1:5003/health"
    "ocr_mutasi     :5004" = "http://127.0.0.1:5004/health"
    "ocr_match      :5005" = "http://127.0.0.1:5005/health"
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
