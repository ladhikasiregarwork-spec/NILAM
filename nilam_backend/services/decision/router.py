from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import build_decision
from .models import DecisionRequest

router = APIRouter()


@router.post("/api/decision")
def decision(req: DecisionRequest) -> dict:
    return ok(**build_decision(req.kemampuanBayar, req.angsuranKpr, req.score, req.grade))
