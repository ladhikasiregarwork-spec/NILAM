from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import build_income
from .models import IncomeRequest

router = APIRouter()


@router.post("/api/income/thp")
def income_thp(req: IncomeRequest) -> dict:
    pasangan_mutasi = req.pasangan.mutasi if req.pasangan else None
    pasangan_angsuran = req.pasangan.angsuranSlik if req.pasangan else 0
    return ok(
        **build_income(
            req.mutasi, req.angsuranSlik, req.joint, pasangan_mutasi, pasangan_angsuran
        )
    )
