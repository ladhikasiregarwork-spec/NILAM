"""FastAPI surface for the orchestrator.

POST /api/v1/applications -> 202 + job_id (work runs in a background task).
GET  /api/v1/applications/{id} -> job status + result.
Plus /health, /upload (poll-based test page), and the OpenAPI 3.0.3 file-field
patch the sibling services use.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, RedirectResponse

from . import __version__, upstream
from .config import get_settings
from .jobs import JobStore
from .models import AcceptedResponse, CollateralInput, JobStatusResponse, LoanRequest
from .pipeline import run_job

logger = logging.getLogger("ocr_orchestrator.api")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="OCR Orchestrator",
    version=__version__,
    description=(
        "NILAM document-bundle orchestrator. Classifies an uploaded PDF pile, "
        "routes each document to the right OCR service, verifies slips against "
        "bank Gaji credits, and aggregates a monthly qualifying-income figure. "
        "Async job + polling."
    ),
)
app.openapi_version = "3.0.3"
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

store = JobStore(get_settings().job_retention)


def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version,
                        openapi_version=app.openapi_version,
                        description=app.description, routes=app.routes)

    def rewrite(node: object) -> None:
        if isinstance(node, dict):
            if (node.get("type") == "string"
                    and node.get("contentMediaType") == "application/octet-stream"):
                node.pop("contentMediaType", None)
                node["format"] = "binary"
            for v in node.values():
                rewrite(v)
        elif isinstance(node, list):
            for item in node:
                rewrite(item)

    rewrite(schema)
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/upload", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


def _validate_numeric(name: str, value: float | None, *, allow_zero: bool) -> None:
    """Reject a provided numeric field that violates its constraint."""
    if value is None:
        return
    if allow_zero and value < 0:
        raise HTTPException(status_code=400, detail=f"{name} must be >= 0.")
    if not allow_zero and value <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be > 0.")


def _validate_appraisal_month(value: int | None) -> None:
    """Reject an appraisal_month that is not a plausible YYYYMM."""
    if value is None:
        return
    year, month = divmod(value, 100)
    if not (1900 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(
            status_code=400,
            detail="appraisal_month must be YYYYMM (e.g. 202606).",
        )


def _build_collateral(
    luas_tanah: float | None, luas_bangunan: float | None,
    kode_pos: str | None, kelurahan: str | None,
    appraisal_month: int | None, warnings: list[str],
) -> CollateralInput | None:
    if luas_tanah is not None and luas_bangunan is not None:
        return CollateralInput(
            luas_tanah=luas_tanah, luas_bangunan=luas_bangunan,
            kode_pos=kode_pos, kelurahan=kelurahan, appraisal_month=appraisal_month,
        )
    if any(v is not None for v in
           (luas_tanah, luas_bangunan, kode_pos, kelurahan, appraisal_month)):
        warnings.append("Partial collateral fields provided (need both luas_tanah "
                        "and luas_bangunan); FMV skipped.")
    return None


def _build_loan(
    loan_amount: float | None, tenor_months: int | None,
    annual_interest_rate: float | None, warnings: list[str],
) -> LoanRequest | None:
    fields = (loan_amount, tenor_months, annual_interest_rate)
    if all(v is not None for v in fields):
        return LoanRequest(loan_amount=loan_amount, tenor_months=tenor_months,
                           annual_interest_rate=annual_interest_rate)
    if any(v is not None for v in fields):
        warnings.append("Partial loan fields provided (need loan_amount, "
                        "tenor_months and annual_interest_rate); decision skipped.")
    return None


@app.post(
    "/api/v1/applications",
    response_model=AcceptedResponse,
    status_code=202,
    tags=["applications"],
    summary="Submit a document bundle; returns a job_id to poll",
)
async def create_application(
    files: List[UploadFile] = File(..., description="The unlabeled PDF bundle."),
    bonus_accept_pct: Optional[float] = Form(
        None, description="Analyst bonus-acceptance fraction 0.0-1.0 (default from config)."),
    password: Optional[str] = Form(None, description="Optional PDF password for protected files."),
    luas_tanah: Optional[float] = Form(None, description="Collateral land area m^2 (> 0)."),
    luas_bangunan: Optional[float] = Form(None, description="Collateral building area m^2 (>= 0)."),
    kode_pos: Optional[str] = Form(None, description="Collateral postal code."),
    kelurahan: Optional[str] = Form(None, description="Collateral village/ward."),
    appraisal_month: Optional[int] = Form(None, description="Appraisal month YYYYMM."),
    loan_amount: Optional[float] = Form(None, description="Requested loan principal (> 0)."),
    tenor_months: Optional[int] = Form(None, description="Loan term in months (> 0)."),
    annual_interest_rate: Optional[float] = Form(None, description="Annual rate as a decimal, e.g. 0.105 (>= 0)."),
) -> AcceptedResponse:
    settings = get_settings()
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one PDF.")
    if len(files) > settings.max_files:
        raise HTTPException(status_code=413,
                            detail=f"Too many files ({len(files)} > MAX_FILES={settings.max_files}).")

    payload: list[tuple[str, bytes]] = []
    for f in files:
        name = f.filename or "unnamed.pdf"
        if not (f.content_type in {"application/pdf", "application/octet-stream"}
                or name.lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail=f"{name!r}: not a PDF.")
        data = await f.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"{name!r}: empty upload.")
        payload.append((name, data))

    if bonus_accept_pct is None:
        pct = settings.default_bonus_accept_pct
    else:
        pct = max(0.0, min(1.0, bonus_accept_pct))  # clamp

    _validate_numeric("luas_tanah", luas_tanah, allow_zero=False)
    _validate_numeric("luas_bangunan", luas_bangunan, allow_zero=True)
    _validate_numeric("loan_amount", loan_amount, allow_zero=False)
    _validate_numeric("tenor_months", tenor_months, allow_zero=False)
    _validate_numeric("annual_interest_rate", annual_interest_rate, allow_zero=True)
    _validate_appraisal_month(appraisal_month)

    input_warnings: list[str] = []
    collateral = _build_collateral(luas_tanah, luas_bangunan, kode_pos, kelurahan,
                                   appraisal_month, input_warnings)
    loan = _build_loan(loan_amount, tenor_months, annual_interest_rate, input_warnings)

    job = await store.create()
    task = asyncio.create_task(
        run_job(store, job.id, payload, bonus_accept_pct=pct, password=password,
                collateral=collateral, loan=loan, input_warnings=input_warnings)
    )
    task.add_done_callback(_log_task_result)
    await store.attach_task(job.id, task)

    return AcceptedResponse(
        job_id=job.id, status=job.status,
        status_url=f"/api/v1/applications/{job.id}",
    )


def _log_task_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("background job crashed: %r", exc)


@app.get(
    "/api/v1/applications/{job_id}",
    response_model=JobStatusResponse,
    tags=["applications"],
    summary="Poll a job's status and (when done) its result",
)
async def get_application(job_id: str) -> JobStatusResponse:
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return JobStatusResponse(
        job_id=job.id, status=job.status, stages=job.stages,
        result=job.result, error=job.error,
    )


_UPLOAD_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>OCR Orchestrator — Upload</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1a1a1a}
 .card{border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:16px}
 label.drop{display:block;border:2px dashed #e5e7eb;border-radius:8px;padding:28px;text-align:center;cursor:pointer}
 label.drop.has{border-color:#059669;background:#f0fdf4}
 input[type=file]{display:none}
 .row{display:flex;gap:16px;align-items:center;margin-top:14px;flex-wrap:wrap}
 input[type=number],input[type=password],input[type=text]{padding:8px;border:1px solid #e5e7eb;border-radius:6px;font:inherit}
 fieldset.grp{border:1px solid #e5e7eb;border-radius:8px;margin:14px 0 0;padding:8px 14px 14px}
 fieldset.grp legend{font-weight:600;font-size:13px;padding:0 6px}
 .opt{font-weight:400;color:#64748b;font-size:12px}
 button{font:inherit;font-weight:600;padding:10px 18px;border:none;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer}
 button:disabled{background:#94a3b8}
 #status{margin:10px 0;font-size:13px}
 pre{background:#0f172a;color:#e2e8f0;padding:16px;border-radius:6px;overflow:auto;font-size:12px;max-height:520px}
 .stages span{display:inline-block;padding:2px 8px;border-radius:4px;margin:2px;font-size:12px;background:#eef2ff;color:#3730a3}
</style></head><body>
<h1>OCR Orchestrator</h1>
<p>Upload the full document bundle (KTP, KK, SK, slip gaji, mutasi). The server
classifies each file, extracts what it can, and returns a monthly income figure.
&nbsp;·&nbsp; <a href="/docs">Swagger</a></p>
<form id="f" class="card">
 <label class="drop" id="drop" for="files"><span class="icon">📄</span>
   <div id="dl">Click to choose PDFs (multi-select)</div>
   <input type="file" id="files" name="files" accept="application/pdf,.pdf" multiple></label>
 <div class="row">
   <label>Bonus accept %: <input type="number" id="pct" min="0" max="100" step="1" value="0" style="width:80px"></label>
   <label>PDF password: <input type="password" id="pw" placeholder="optional"></label>
 </div>
 <fieldset class="grp"><legend>Collateral <span class="opt">— optional; needs both luas_tanah + luas_bangunan to price FMV</span></legend>
  <div class="row">
   <label>Luas tanah m²: <input type="number" id="lt" min="0" step="0.01" placeholder="80" style="width:100px"></label>
   <label>Luas bangunan m²: <input type="number" id="lb" min="0" step="0.01" placeholder="50" style="width:100px"></label>
   <label>Kode pos: <input type="text" id="kp" placeholder="40123" style="width:100px"></label>
   <label>Kelurahan: <input type="text" id="kl" placeholder="antapani kidul" style="width:160px"></label>
   <label>Appraisal month: <input type="number" id="am" min="200001" max="209912" placeholder="202606" style="width:110px"></label>
  </div>
 </fieldset>
 <fieldset class="grp"><legend>Loan <span class="opt">— optional; needs all three for the approve/refer decision</span></legend>
  <div class="row">
   <label>Loan amount: <input type="number" id="la" min="0" step="1000000" placeholder="500000000" style="width:140px"></label>
   <label>Tenor months: <input type="number" id="tn" min="1" step="1" placeholder="180" style="width:100px"></label>
   <label>Annual interest: <input type="number" id="ir" min="0" step="0.001" placeholder="0.105" style="width:100px"></label>
  </div>
 </fieldset>
 <div class="row">
   <button type="submit" id="go">Submit</button>
 </div>
 <div id="status"></div>
 <div class="stages" id="stages"></div>
</form>
<pre id="out">(no request sent yet)</pre>
<script>
const f=document.getElementById('f'),fi=document.getElementById('files'),drop=document.getElementById('drop'),
 dl=document.getElementById('dl'),st=document.getElementById('status'),out=document.getElementById('out'),
 go=document.getElementById('go'),stages=document.getElementById('stages');
fi.addEventListener('change',()=>{if(fi.files.length){drop.classList.add('has');dl.textContent=fi.files.length+' file(s) selected';}});
function renderStages(s){stages.innerHTML=(s||[]).map(x=>`<span>${x.name}: ${x.status}</span>`).join('');}
async function poll(url){
 for(let i=0;i<600;i++){
   const r=await fetch(url);const d=await r.json();
   renderStages(d.stages);out.textContent=JSON.stringify(d,null,2);
   if(d.status==='completed'||d.status==='failed'){st.textContent='Status: '+d.status;return;}
   st.textContent='Status: '+d.status+' …';await new Promise(z=>setTimeout(z,1000));
 }
}
f.addEventListener('submit',async e=>{e.preventDefault();
 if(!fi.files.length){st.textContent='Pick at least one PDF.';return;}
 const fd=new FormData();for(const x of fi.files)fd.append('files',x,x.name);
 fd.append('bonus_accept_pct',(Number(document.getElementById('pct').value)||0)/100);
 const pw=document.getElementById('pw').value;if(pw)fd.append('password',pw);
 const add=(id,key)=>{const v=document.getElementById(id).value.trim();if(v!=='')fd.append(key,v);};
 add('lt','luas_tanah');add('lb','luas_bangunan');add('kp','kode_pos');add('kl','kelurahan');add('am','appraisal_month');
 add('la','loan_amount');add('tn','tenor_months');add('ir','annual_interest_rate');
 go.disabled=true;st.textContent='Submitting…';stages.innerHTML='';
 try{
   const r=await fetch('/api/v1/applications',{method:'POST',body:fd});
   const d=await r.json();
   if(r.status!==202){st.textContent='HTTP '+r.status+' — '+(d.detail||'error');out.textContent=JSON.stringify(d,null,2);return;}
   st.textContent='Accepted — polling…';await poll(d.status_url);
 }catch(err){st.textContent='Network error: '+err;}finally{go.disabled=false;}
});
</script></body></html>"""


@app.get("/upload", response_class=HTMLResponse, include_in_schema=False)
def upload_page() -> HTMLResponse:
    return HTMLResponse(_UPLOAD_PAGE)
