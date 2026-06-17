from fastapi import APIRouter
from fastapi.responses import JSONResponse

from nilam_backend.core.envelope import err, ok
from nilam_backend.core.jobs import STORE

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
