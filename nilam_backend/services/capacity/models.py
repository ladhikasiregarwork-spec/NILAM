from pydantic import BaseModel


class CapacityRequest(BaseModel):
    gajiBulanan: float
    thrTahunan: float = 0
    bonusTahunan: float = 0
    angsuranSlik: float = 0
