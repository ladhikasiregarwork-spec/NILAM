from typing import List, Optional

from pydantic import BaseModel

from nilam_backend.domain.agunan import AgunanKlasifikasi
from nilam_backend.domain.documents import MutasiExtract, SlipRecord


class OcrInput(BaseModel):
    mutasi: MutasiExtract = MutasiExtract()
    slipRecords: List[SlipRecord] = []


class UserInputModel(BaseModel):
    nik: Optional[str] = None
    nama: Optional[str] = None
    pendidikan: Optional[str] = None
    statusKawin: Optional[str] = None
    usia: Optional[int] = None
    jangkaWaktu: Optional[int] = None
    uangMuka: float = 0
    jumlahTanggungan: Optional[int] = None
    punyaSimpananBri: bool = False


class AgunanModel(BaseModel):
    harga: float = 0
    luasTanah: Optional[float] = None
    luasBangunan: Optional[float] = None
    kelurahan: Optional[str] = None
    kodepos: Optional[str] = None


class ProcessRequest(BaseModel):
    joint: bool = False
    uploads: List[str] = []
    ocr: OcrInput = OcrInput()
    pasanganOcr: Optional[OcrInput] = None
    userInput: UserInputModel = UserInputModel()
    agunan: AgunanModel = AgunanModel()
    agunanKlas: AgunanKlasifikasi = AgunanKlasifikasi()
    # NPW (fair value) precomputed by the upstream npw service / from-link; 0 if unknown.
    npw: float = 0


class SurveyRequest(BaseModel):
    decision: str            # "approved" | "rejected"
    value: Optional[float] = None
    note: Optional[str] = None
