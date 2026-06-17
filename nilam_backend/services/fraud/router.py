from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import detect_fraud
from .models import FraudRequest

router = APIRouter()


@router.post("/api/fraud")
def fraud(req: FraudRequest) -> dict:
    return ok(**detect_fraud(req.slip, req.mutasi, req.identity))
