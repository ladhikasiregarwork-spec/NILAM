from nilam_backend.core.money import js_round
from nilam_backend.data.ltv_grid import ltv_from_klas
from nilam_backend.domain.agunan import AgunanKlasifikasi


def build_plafond(
    npw: float, harga: float, uang_muka: float, klas: AgunanKlasifikasi
) -> dict:
    """plafon agunan = round(NPW * LTV); kebutuhan = max(0, harga - DP);
    penambahan DP = max(0, kebutuhan - plafon agunan)."""
    ltv = ltv_from_klas(klas, harga)
    plafon_agunan = js_round(npw * ltv)
    kebutuhan = max(0, harga - uang_muka)
    penambahan_dp = max(0, kebutuhan - plafon_agunan)
    return {
        "ltv": ltv,
        "plafonAgunan": plafon_agunan,
        "kebutuhan": kebutuhan,
        "penambahanDp": penambahan_dp,
    }
