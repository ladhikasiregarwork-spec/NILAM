from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import analyze_ocr_coverage
from .models import CoverageRequest

router = APIRouter()


@router.post("/api/validation/coverage")
def coverage(req: CoverageRequest) -> dict:
    return ok(**analyze_ocr_coverage(req.detectedMonths, req.minMonths))
