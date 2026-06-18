import json
from typing import List

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from nilam_backend.core.envelope import err, ok
from nilam_backend.core.jobs import STORE

from .ingest import ingest_bundle
from .models import ProcessRequest
from .pipeline import run_pipeline

router = APIRouter()


@router.post("/api/applications/{app_id}/process")
def process(app_id: str, req: ProcessRequest) -> dict:
    """Create the job and drive the pipeline to completion (in-process, fast).
    Events + the assembled ApplicationView are then available via the GET routes."""
    job = STORE.create(app_id)
    view = run_pipeline(job, req)
    return ok(applicationId=app_id, status=job.status, eventCount=len(job.events), view=view)


@router.post("/api/applications/{app_id}/process-bundle")
async def process_bundle(
    app_id: str,
    files: List[UploadFile] = File(...),
    meta: str = Form("{}"),
) -> dict:
    """Raw-bundle entry point: the backend owns OCR. Accepts the uploaded PDFs plus
    a JSON `meta` part ({joint, userInput, agunan, agunanKlas}); classifies/extracts
    them via the upstream OCR services, then drives the same pipeline as `process`."""
    try:
        meta_dict = json.loads(meta or "{}")
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content=err("meta bukan JSON yang valid"))

    uploads = [(f.filename or "dokumen.pdf", await f.read(), f.content_type or "application/pdf")
               for f in files]
    req, audit = await ingest_bundle(uploads, meta_dict)

    job = STORE.create(app_id)
    view = run_pipeline(job, req)
    return ok(applicationId=app_id, status=job.status, eventCount=len(job.events),
              view=view, audit=audit)


@router.get("/api/applications/{app_id}/events")
def events(app_id: str):
    job = STORE.get(app_id)
    if job is None:
        return JSONResponse(status_code=404, content=err("application tidak ditemukan"))
    return ok(applicationId=app_id, status=job.status, events=job.events)


@router.get("/api/applications/{app_id}")
def application(app_id: str):
    job = STORE.get(app_id)
    if job is None:
        return JSONResponse(status_code=404, content=err("application tidak ditemukan"))
    return ok(applicationId=app_id, status=job.status, view=job.result, survey=job.survey)
