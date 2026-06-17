from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from nilam_backend.core.envelope import err, ok

from .logic import get_slik

router = APIRouter()


@router.get("/api/slik")
def slik(nik: str = Query(default="")):
    if not nik:
        return JSONResponse(status_code=400, content=err("nik wajib diisi"))
    return ok(report=get_slik(nik))
