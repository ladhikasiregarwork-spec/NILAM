from typing import Optional

from nilam_backend.domain.agunan import (
    AgunanKlasifikasi,
    DeveloperTier,
    PropertiTipe,
    RangeHarga,
    RumahLamaJenis,
    UkuranTipe,
)

# LTV_BARU[tier][properti][ukuran]
LTV_BARU: dict[DeveloperTier, dict[PropertiTipe, dict[UkuranTipe, float]]] = {
    "tier1": {
        "tapak": {"gt70": 0.95, "mid": 0.95, "lt21": 0.95},
        "apartemen": {"gt70": 0.85, "mid": 0.9, "lt21": 0.9},
        "ruko": {"gt70": 0.9, "mid": 0.9, "lt21": 0.9},
    },
    "local_champion": {
        "tapak": {"gt70": 0.9, "mid": 0.9, "lt21": 0.9},
        "apartemen": {"gt70": 0.8, "mid": 0.85, "lt21": 0.85},
        "ruko": {"gt70": 0.85, "mid": 0.85, "lt21": 0.85},
    },
    "tier2": {
        "tapak": {"gt70": 0.9, "mid": 0.9, "lt21": 0.9},
        "apartemen": {"gt70": 0.85, "mid": 0.85, "lt21": 0.85},
        "ruko": {"gt70": 0.8, "mid": 0.8, "lt21": 0.8},
    },
    "tier3": {
        "tapak": {"gt70": 0.85, "mid": 0.85, "lt21": 0.85},
        "apartemen": {"gt70": 0.8, "mid": 0.8, "lt21": 0.8},
        "ruko": {"gt70": 0.75, "mid": 0.75, "lt21": 0.75},
    },
}

LTV_SECONDARY: dict[RangeHarga, float] = {"lt5": 0.9, "mid": 0.85, "gt15": 0.8}
LTV_REFINANCING = 0.7


def range_harga(harga: Optional[float]) -> RangeHarga:
    if harga is None:
        return "mid"
    if harga < 5_000_000_000:
        return "lt5"
    if harga <= 15_000_000_000:
        return "mid"
    return "gt15"


def ltv_baru(tier: DeveloperTier, prop: PropertiTipe, ukuran: UkuranTipe) -> float:
    return LTV_BARU[tier][prop][ukuran]


def ltv_lama(jenis: RumahLamaJenis, harga: Optional[float] = None) -> float:
    return LTV_REFINANCING if jenis == "refinancing" else LTV_SECONDARY[range_harga(harga)]


def ltv_from_klas(k: AgunanKlasifikasi, harga: Optional[float] = None) -> float:
    if k.kategori == "baru":
        return ltv_baru(k.tier, k.prop, k.ukuran)
    return ltv_lama(k.jenisLama, harga)
