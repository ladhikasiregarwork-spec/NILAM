from fastapi import APIRouter

from nilam_backend.core.envelope import ok
from nilam_backend.domain.documents import SlipGajiExtract
from nilam_backend.projection.matching import build_match

from .models import MatchingRequest

router = APIRouter()


@router.post("/api/matching")
def matching(req: MatchingRequest) -> dict:
    res = build_match(req.mutasi, SlipGajiExtract(records=req.slipRecords))
    return ok(monthlyRecap=res["recaps"], incomeTransactions=res["txns"])
