from pathlib import Path
from house_fair_market_value.config import load_config

BASE = Path(__file__).resolve().parents[1]

def test_config_has_required_keys_and_edges():
    cfg = load_config(BASE)
    for key in ["backend", "current_month", "reference_min_month_index",
                "area_bucket_edges", "lookup_keys", "models", "location_lookup_path"]:
        assert key in cfg, f"missing config key: {key}"
    assert cfg["backend"] in {"linear", "catboost"}
    assert cfg["reference_min_month_index"] == 24308
    land = cfg["area_bucket_edges"]["land_area_bucket"]
    assert len(land) == 6 and land[0] == 44.75
    assert set(cfg["models"]) == {"linear", "catboost"}

def test_required_artifacts_exist():
    cfg = load_config(BASE)
    assert (BASE / cfg["location_lookup_path"]).exists()
    for backend in ("linear", "catboost"):
        for part in ("tanah", "bangunan"):
            assert (BASE / cfg["models"][backend][part]).exists()
