"""RM survey / field appraisal (service 18). Human-in-the-loop gate for collateral
priced >= SURVEY_THRESHOLD. On approval the RM's appraised value OVERRIDES NPW and
the offer is recomputed; rejection halts the flow at the survey step.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from nilam_backend.core.envelope import err, ok
from nilam_backend.core.jobs import STORE

from ..orchestration.models import SurveyRequest
from ..orchestration.pipeline import recompute_with_npw

router = APIRouter()


@router.get("/api/applications/{app_id}/survey")
def get_survey(app_id: str):
    job = STORE.get(app_id)
    if job is None:
        return JSONResponse(status_code=404, content=err("application tidak ditemukan"))
    return ok(**job.survey)


@router.post("/api/applications/{app_id}/survey")
def post_survey(app_id: str, req: SurveyRequest):
    job = STORE.get(app_id)
    if job is None:
        return JSONResponse(status_code=404, content=err("application tidak ditemukan"))

    if req.decision == "approved":
        job.survey = {"status": "approved", "surveyValue": req.value, "surveyNote": req.note}
        # RM value overrides NPW -> recompute the offer/decision.
        if req.value is not None:
            recompute_with_npw(job, req.value)
    elif req.decision == "rejected":
        job.survey = {"status": "rejected", "surveyValue": req.value, "surveyNote": req.note}
    else:
        return JSONResponse(status_code=400, content=err("decision harus 'approved' atau 'rejected'"))

    return ok(**job.survey)
