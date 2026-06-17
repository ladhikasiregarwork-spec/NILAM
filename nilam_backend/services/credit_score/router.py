from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import compute_credit_score
from .models import CreditScoreInput

router = APIRouter()


@router.post("/api/credit-score")
def credit_score(req: CreditScoreInput) -> dict:
    return ok(**compute_credit_score(req))
