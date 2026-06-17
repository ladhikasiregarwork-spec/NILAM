import math
from typing import Optional

from nilam_backend.data.kpr_rates import FLOATING_RATE, KPR_SCHEMES, KprScheme, rate_plan

from .kpr_math import build_schedule, max_plafond, max_tenor_by_age

ALT_TENORS = [5, 10, 15, 20, 25]
RETIREMENT = 56


def build_offering(
    harga: float,
    uang_muka: float,
    usia: Optional[int],
    jangka_waktu: Optional[int],
    kemampuan: Optional[float],
    plafon_agunan: Optional[float],
) -> dict:
    """Port of OfferingScreen: plafon dibiayai = min(requested, NPW*LTV cap,
    capacity cap). Shortfall becomes tambahan DP. Each scheme exposes its
    fixed->floating schedule across the valid tenors."""
    requested = max(0, harga - uang_muka)
    tenor_maks = max_tenor_by_age(usia, RETIREMENT)
    tenor_nasabah = max(1, min(jangka_waktu if jangka_waktu else 15, tenor_maks))
    cap_collateral = plafon_agunan if (plafon_agunan and plafon_agunan > 0) else math.inf

    def calc(scheme: KprScheme, t: int) -> dict:
        months = t * 12
        plan = rate_plan(scheme, t)
        rate_promo = plan[0]["rate"] if plan else scheme.rate
        cap_afford = (
            max_plafond(kemampuan, rate_promo, months)
            if (kemampuan and kemampuan > 0)
            else math.inf
        )
        cap = min(cap_collateral, cap_afford)
        plafon_final = min(requested, cap)  # finite: requested is finite
        schedule = build_schedule(plafon_final, t, plan) if plafon_final > 0 else []
        tambahan_dp = max(0, requested - cap)  # 0 when cap is inf
        return {
            "tenor": t,
            "angsuran": schedule[0]["angsuran"] if schedule else 0,
            "schedule": schedule,
            "plafonFinal": plafon_final,
            "tambahanDp": tambahan_dp,
            "ok": tambahan_dp <= 0,
        }

    schemes_out: list[dict] = []
    candidate_tenors = sorted({tenor_nasabah, *ALT_TENORS})
    for s in KPR_SCHEMES:
        if s.minTenor > tenor_maks:
            continue
        upper = min(s.maxTenor, tenor_maks)
        tenor_options = [calc(s, t) for t in candidate_tenors if s.minTenor <= t <= upper]
        if not tenor_options:
            continue
        schemes_out.append(
            {
                "scheme": s.id,
                "label": s.label,
                "rateLabel": s.rateLabel,
                "note": s.note,
                "tenorOptions": tenor_options,
            }
        )

    return {
        "maxTenorByAge": tenor_maks,
        "requested": requested,
        "tenorNasabah": tenor_nasabah,
        "floatingRate": FLOATING_RATE,
        "schemes": schemes_out,
    }
