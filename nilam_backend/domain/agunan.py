from typing import Literal

from pydantic import BaseModel

AgunanKategori = Literal["baru", "lama"]
DeveloperTier = Literal["tier1", "local_champion", "tier2", "tier3"]
PropertiTipe = Literal["tapak", "apartemen", "ruko"]
UkuranTipe = Literal["gt70", "mid", "lt21"]  # >70 · 21-70 · <21
RumahLamaJenis = Literal["secondary", "refinancing"]
RangeHarga = Literal["lt5", "mid", "gt15"]


class AgunanKlasifikasi(BaseModel):
    """Editable collateral classification, shared across dashboard + offer."""

    kategori: AgunanKategori = "baru"
    tier: DeveloperTier = "tier1"
    prop: PropertiTipe = "tapak"
    ukuran: UkuranTipe = "gt70"
    jenisLama: RumahLamaJenis = "secondary"
