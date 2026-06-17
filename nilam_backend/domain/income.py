"""Income contracts = the UI's `types/income.ts` shapes."""

from typing import List, Literal

from pydantic import BaseModel

ComponentKey = Literal["Gaji", "THR", "Bonus", "Insentif"]
ComponentMode = Literal["avg", "min"]


class IncomeComponent(BaseModel):
    """One income component derived from the mutasi credit classification."""

    key: ComponentKey
    avg: int
    min: int
    mode: ComponentMode = "avg"
    weight: float = 1


class CustomerIncomeThp(BaseModel):
    """A single applicant leg's income result: components + take-home pay."""

    components: List[IncomeComponent]
    thp: int
