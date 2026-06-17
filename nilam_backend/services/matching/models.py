from typing import List, Optional

from pydantic import BaseModel

from nilam_backend.domain.documents import MutasiExtract, SlipRecord


class MatchingRequest(BaseModel):
    mutasi: Optional[MutasiExtract] = None
    slipRecords: List[SlipRecord] = []
