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
from .models import AcceptedResponse, JobStatusResponse
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

    job = await store.create()
    task = asyncio.create_task(
        run_job(store, job.id, payload, bonus_accept_pct=pct, password=password)
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
 input[type=number],input[type=password]{padding:8px;border:1px solid #e5e7eb;border-radius:6px;font:inherit}
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
