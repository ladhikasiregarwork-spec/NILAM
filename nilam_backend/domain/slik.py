"""SLIK / credit-bureau contracts = the UI's `types/profile.ts` shapes."""

from typing import List, Optional

from pydantic import BaseModel


class SlikLoan(BaseModel):
    """One credit facility reported by SLIK OJK."""

    jenis: str                      # "KPR" | "KKB" | "Kartu Kredit" | "KTA"
    lembaga: str
    plafon: float                   # approved limit
    baki: float                     # outstanding balance (baki debet)
    angsuran: float                 # monthly installment
    status: str                     # collectibility status, e.g. "Lancar"
    kualitas: int                   # collectibility class 1..5
    sukuBunga: Optional[float] = None
    tanggalMulai: Optional[str] = None
    tanggalJatuhTempo: Optional[str] = None
    aktif: Optional[bool] = None


class SlikReport(BaseModel):
    """Parsed SLIK report, keyed by NIK."""

    nik: str
    namaDebitur: Optional[str] = None
    loans: List[SlikLoan] = []
    totalAngsuran: float = 0        # sum of active facilities' installments -> feeds capacity/THP
    kolekTerburuk: int = 1          # worst collectibility (1 best .. 5 macet)
    totalFasilitas: int = 0         # number of facilities
