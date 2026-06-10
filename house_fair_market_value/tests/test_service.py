from pathlib import Path

import pandas as pd
import pytest

from house_fair_market_value.service import FairValueService

BASE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def service():
    return FairValueService(BASE)


def _known_location():
    lookup = pd.read_parquet(BASE / "artifacts" / "location_feature_lookup.parquet")
    row = lookup.iloc[0]
    return str(row["kodepos_agunan"]), str(row["kelurahan_standardized"])


def test_predict_one_matched_location(service):
    kode_pos, kelurahan = _known_location()
    out = service.predict_one({"luas_tanah": 80.0, "luas_bangunan": 50.0,
                               "kode_pos": kode_pos, "kelurahan": kelurahan})
    assert out["location_matched"] is True
    assert out["land_value"] > 0 and out["building_value"] > 0
    assert out["fair_value"] == pytest.approx(out["land_value"] + out["building_value"], rel=1e-9)
    assert out["backend"] == "linear"


def test_land_only_zeroes_building(service):
    kode_pos, kelurahan = _known_location()
    out = service.predict_one({"luas_tanah": 120.0, "luas_bangunan": 0.0,
                               "kode_pos": kode_pos, "kelurahan": kelurahan})
    assert out["building_value"] == 0.0
    assert out["fair_value"] == pytest.approx(out["land_value"], rel=1e-9)


def test_unknown_location_warns(service):
    out = service.predict_one({"luas_tanah": 80.0, "luas_bangunan": 50.0,
                               "kode_pos": "00000", "kelurahan": "zzz_no_such_place"})
    assert out["location_matched"] is False
    assert any("Location not found" in w for w in out["warnings"])
