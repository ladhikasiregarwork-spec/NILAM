from typing import Optional

from pydantic import BaseModel


class CreditScoreInput(BaseModel):
    pendidikan: Optional[str] = None
    statusKawin: Optional[str] = None
    usia: Optional[int] = None
    punyaSimpananBri: Optional[bool] = None
    jangkaWaktu: Optional[int] = None
    hargaRumah: Optional[float] = None
    uangMuka: Optional[float] = None
    jumlahTanggungan: Optional[int] = None
    incomeMonthly: Optional[float] = None
    angsuranBulanan: Optional[float] = None
    plafond: Optional[float] = None
