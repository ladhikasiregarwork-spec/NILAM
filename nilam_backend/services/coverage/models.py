from typing import List

from pydantic import BaseModel


class CoverageRequest(BaseModel):
    detectedMonths: List[str] = []   # e.g. ["2025-01", "2025-02", ...]
    minMonths: int = 0               # 12 for mutasi, 0 (or 3) for slip
