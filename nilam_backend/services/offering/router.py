from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import build_offering
from .models import OfferingRequest

router = APIRouter()


@router.post("/api/offering")
def offering(req: OfferingRequest) -> dict:
    return ok(
        **build_offering(
            req.harga, req.uangMuka, req.usia, req.jangkaWaktu, req.kemampuan, req.plafonAgunan
        )
    )
