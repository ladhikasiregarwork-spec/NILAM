from typing import List, Optional

from pydantic import BaseModel

from nilam_backend.domain.documents import MutasiExtract, SlipRecord


class IncomeLegInput(BaseModel):
    mutasi: MutasiExtract
    # slipRecords accepted for contract completeness; THP derives from mutasi.
    slipRecords: List[SlipRecord] = []
    angsuranSlik: float = 0


class IncomeRequest(BaseModel):
    mutasi: MutasiExtract
    slipRecords: List[SlipRecord] = []
    angsuranSlik: float = 0
    joint: bool = False
    pasangan: Optional[IncomeLegInput] = None
