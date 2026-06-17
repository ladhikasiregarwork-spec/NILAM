from pydantic import BaseModel


class DecisionRequest(BaseModel):
    kemampuanBayar: float = 0
    angsuranKpr: float = 0
    plafond: float = 0          # context only (echoed/ignored by the synthesis)
    uangMuka: float = 0
    incomeMonthly: float = 0
    tenor: int = 0
    score: int = 0
    grade: str = ""
