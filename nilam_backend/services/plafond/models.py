from pydantic import BaseModel

from nilam_backend.domain.agunan import AgunanKlasifikasi


class PlafondRequest(BaseModel):
    npw: float
    harga: float = 0
    uangMuka: float = 0
    klasifikasi: AgunanKlasifikasi
