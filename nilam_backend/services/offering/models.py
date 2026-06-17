from typing import Optional

from pydantic import BaseModel


class OfferingRequest(BaseModel):
    harga: float = 0              # agunan price
    uangMuka: float = 0           # down payment
    usia: Optional[int] = None    # borrower age in years (caller computes from KTP date)
    jangkaWaktu: Optional[int] = None
    kemampuan: Optional[float] = None      # output of /api/capacity
    plafonAgunan: Optional[float] = None   # output of /api/agunan/plafond
