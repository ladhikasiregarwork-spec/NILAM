"""Shared document contracts = the UI's OCR-extract shapes.

These mirror `nilam-prototype/types/ocrExtract.ts`. The new backend's upstream
normalizers (Phase 6) produce these shapes from the raw `ocr_*` payloads; the
calc/projection services consume them.
"""

from typing import List, Optional, Union

from pydantic import BaseModel


class MutasiTxn(BaseModel):
    """One transaction parsed from a bank statement (mutasi rekening)."""

    tanggal: str
    remark: str = ""
    nominal: float = 0
    dk: str = ""           # "Debit" | "Kredit"
    klasifikasi: str = ""  # "Gaji" | "THR" | "Bonus" | "Insentif" | "Lainnya"


class MutasiExtract(BaseModel):
    """Bank-statement extraction result (merged across months)."""

    transactions: List[MutasiTxn] = []
    noRekening: Optional[str] = None
    count: int = 0
    totalKredit: float = 0
    totalDebet: float = 0
    gajiNominal: Optional[float] = None
    ringkasan: Optional[dict] = None
    fileName: Optional[Union[str, List[str]]] = None


class SlipRecord(BaseModel):
    """One salary slip = one payment date."""

    tanggalPembayaran: Optional[str] = None
    totalUpah: Optional[float] = None
    totalPotongan: Optional[float] = None
    thp: Optional[float] = None          # take-home pay = totalUpah - totalPotongan
    thr: Optional[float] = None
    bonus: Optional[float] = None
    gajiPokok: Optional[float] = None
    tunjangan: Optional[float] = None
    potonganBonus: Optional[float] = None
    potonganThr: Optional[float] = None
    potonganCuti: Optional[float] = None
    fileName: Optional[str] = None


class SlipGajiExtract(BaseModel):
    """Salary-slip extraction: one record per uploaded slip (per payment date)."""

    records: List[SlipRecord] = []
