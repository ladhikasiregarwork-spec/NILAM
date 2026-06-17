from fastapi import APIRouter

from nilam_backend.core.envelope import ok

from .logic import dir_rate, kemampuan_bayar, penghasilan_bulanan
from .models import CapacityRequest

router = APIRouter()


@router.post("/api/capacity")
def capacity(req: CapacityRequest) -> dict:
    penghasilan = penghasilan_bulanan(req.gajiBulanan, req.thrTahunan, req.bonusTahunan)
    return ok(
        penghasilanBulanan=penghasilan,
        dirRate=dir_rate(penghasilan),
        kemampuanBayar=kemampuan_bayar(
            req.gajiBulanan, req.thrTahunan, req.bonusTahunan, req.angsuranSlik
        ),
    )
