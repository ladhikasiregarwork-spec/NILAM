"""house_fair_market_value (:8000) /predict -> UI NPW shape.

Flat response, snake->camel only: fair_value->fairValue, land_value->landValue,
building_value->buildingValue, location_matched->locationMatched.
"""

from typing import Optional

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_json


def normalize_npw(raw: dict) -> dict:
    return {
        "fairValue": raw.get("fair_value"),
        "landValue": raw.get("land_value"),
        "buildingValue": raw.get("building_value"),
        "locationMatched": bool(raw.get("location_matched", False)),
        "backend": raw.get("backend"),
        "warnings": raw.get("warnings", []) or [],
    }


async def fetch_npw(
    luas_tanah: float,
    luas_bangunan: Optional[float] = None,
    kode_pos: Optional[str] = None,
    kelurahan: Optional[str] = None,
) -> dict:
    s = get_settings()
    payload = {
        "luas_tanah": luas_tanah,
        "luas_bangunan": luas_bangunan,
        "kode_pos": kode_pos,
        "kelurahan": kelurahan,
    }
    raw = await post_json("{}/predict".format(s.npw_url), json=payload, service="npw")
    return normalize_npw(raw)
