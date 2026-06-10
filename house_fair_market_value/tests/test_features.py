import numpy as np
import pandas as pd
import pytest

from house_fair_market_value import features as F


def test_property_features_match_src():
    from src.feature_engineering import create_property_features as src_fn
    df = pd.DataFrame([{"luas_tanah": 78.0, "luas_bangunan": 48.0},
                       {"luas_tanah": 120.0, "luas_bangunan": 0.0}])
    cfg = {"target_column": "nilai_pasar_wajar",
           "land_area_column": "luas_tanah", "building_area_column": "luas_bangunan"}
    expected = src_fn(df, cfg, include_target=False)
    got = F.create_property_features(df, "luas_tanah", "luas_bangunan")
    for col in ["log_land_area", "log_building_area", "building_to_land_ratio", "is_land_only"]:
        np.testing.assert_allclose(
            pd.to_numeric(got[col]).to_numpy(dtype=float),
            pd.to_numeric(expected[col]).to_numpy(dtype=float),
            rtol=1e-12, equal_nan=True)


def test_location_ratio_features_match_src():
    from src.feature_engineering import create_location_features as src_fn
    df = pd.DataFrame([{"sum_pria": 1000.0, "sum_wanita": 1100.0,
                        "sum_jumlah_penduduk": 2100.0, "sum_jumlah_kk": 600.0,
                        "sum_pinjaman_loan": 5_000_000.0, "sum_luas_wilayah": 12.5}])
    expected = src_fn(df, {})
    got = F.create_location_features(df)
    for col in ["female_ratio", "male_ratio", "loan_per_family",
                "loan_per_capita", "population_density", "family_density"]:
        np.testing.assert_allclose(float(got[col].iloc[0]), float(expected[col].iloc[0]), rtol=1e-12)


def test_time_features_match_src():
    from src.feature_engineering import create_time_features as src_fn
    df = pd.DataFrame([{"appraisal_date": pd.Timestamp("2026-06-01")}])
    expected, _ = src_fn(df, {}, reference_min_month_index=24308)
    got = F.create_time_features(df, 24308)
    for col in ["appraisal_year", "appraisal_month_num", "month_index", "month_num_since_start"]:
        assert int(got[col].iloc[0]) == int(expected[col].iloc[0])


def test_area_buckets_match_src_label_strings():
    from src.feature_engineering import apply_area_bucket_edges as src_fn
    edges = {"land_area_bucket": [44.75, 62.0, 72.0, 84.0, 105.0, 216.45],
             "building_area_bucket": [29.95, 36.0, 45.0, 52.2, 75.0, 191.5]}
    df = pd.DataFrame([{"luas_tanah": 78.0, "luas_bangunan": 48.0},
                       {"luas_tanah": 5000.0, "luas_bangunan": 0.0}])
    cfg = {"land_area_column": "luas_tanah", "building_area_column": "luas_bangunan"}
    expected = src_fn(df, cfg, edges)
    got = F.apply_area_bucket_edges(df, edges, "luas_tanah", "luas_bangunan")
    assert list(got["land_area_bucket"].astype(str)) == list(expected["land_area_bucket"].astype(str))
    assert list(got["building_area_bucket"].astype(str)) == list(expected["building_area_bucket"].astype(str))


def test_parse_appraisal_month_yyyymm():
    out = F.parse_appraisal_month(pd.Series(["202606"]))
    assert out.iloc[0] == pd.Timestamp("2026-06-01")


def test_standardize_key():
    out = F.standardize_key(pd.Series(["  Menteng  Dalam "]))
    assert out.iloc[0] == "menteng dalam"


def test_enrich_hits_known_key_and_fills_columns():
    import pandas as pd
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    lookup = pd.read_parquet(base / "artifacts" / "location_feature_lookup.parquet")
    sample = lookup.iloc[0]
    df = pd.DataFrame([{
        "luas_tanah": 80.0, "luas_bangunan": 50.0,
        "kodepos_agunan": sample["kodepos_agunan"],
        "kelurahan_standardized": sample["kelurahan_standardized"],
    }])
    enriched, matched = F.enrich_with_location_lookup(df, lookup, ["kodepos_agunan", "kelurahan_standardized"])
    assert matched is True
    location_cols = [c for c in lookup.columns if c not in ("kodepos_agunan", "kelurahan_standardized")]
    assert enriched[location_cols].notna().any(axis=1).iloc[0]


def test_enrich_miss_returns_false():
    import pandas as pd
    from pathlib import Path
    base = Path(__file__).resolve().parents[1]
    lookup = pd.read_parquet(base / "artifacts" / "location_feature_lookup.parquet")
    df = pd.DataFrame([{
        "luas_tanah": 80.0, "luas_bangunan": 50.0,
        "kodepos_agunan": "00000", "kelurahan_standardized": "zzz_no_such_place",
    }])
    enriched, matched = F.enrich_with_location_lookup(df, lookup, ["kodepos_agunan", "kelurahan_standardized"])
    assert matched is False


def test_assemble_features_produces_buckets_and_time():
    import pandas as pd
    from pathlib import Path
    from house_fair_market_value.config import load_config
    base = Path(__file__).resolve().parents[1]
    cfg = load_config(base)
    lookup = pd.read_parquet(base / cfg["location_lookup_path"])
    raw = {"luas_tanah": 78.0, "luas_bangunan": 48.0,
           "kodepos_agunan": None, "kelurahan_standardized": None, "appraisal_month": 202606}
    df, matched = F.assemble_features(raw, lookup, cfg)
    assert matched is False
    assert df["month_num_since_start"].iloc[0] == 24318 - 24308
    assert str(df["land_area_bucket"].iloc[0]) == "(72.0, 84.0]"
    assert df["is_land_only"].iloc[0] == 0
