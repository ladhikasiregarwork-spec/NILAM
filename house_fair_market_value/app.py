from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import FairValueService

BASE_DIR = Path(__file__).resolve().parent
service = FairValueService(BASE_DIR)
app = FastAPI(title="House Price Fair Value API", version="1.0.0")


class PredictRequest(BaseModel):
    luas_tanah: float = Field(..., gt=0, description="Land area in m^2 (required, > 0)")
    luas_bangunan: float = Field(..., ge=0, description="Building area in m^2 (0 = land only)")
    kode_pos: Optional[str] = Field(None, description="Postal code (kodepos_agunan)")
    kelurahan: Optional[str] = Field(None, description="Standardized village/ward name")
    appraisal_month: Optional[int] = Field(None, description="YYYYMM; defaults to config current_month")


class PredictResponse(BaseModel):
    land_value: float
    building_value: float
    fair_value: float
    location_matched: bool
    backend: str
    warnings: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "backend": service.cfg["backend"]}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    try:
        return PredictResponse(**service.predict_one(request.model_dump()))
    except Exception as exc:  # noqa: BLE001 - surface assembly/model errors as 400
        raise HTTPException(status_code=400, detail=str(exc))
