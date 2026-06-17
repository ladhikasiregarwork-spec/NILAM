from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import build_plafond
from .models import PlafondRequest

router = APIRouter()


@router.post("/api/agunan/plafond")
def plafond(req: PlafondRequest) -> dict:
    return ok(**build_plafond(req.npw, req.harga, req.uangMuka, req.klasifikasi))
