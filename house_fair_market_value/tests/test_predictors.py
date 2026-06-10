import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from house_fair_market_value.predictors import LinearJSONPredictor

BASE = Path(__file__).resolve().parents[1]
TANAH = BASE / "artifacts" / "alternate_tanah_linear_regression_log_price.json"


def _spec():
    return json.loads(TANAH.read_text(encoding="utf-8"))


def _sklearn_oracle(spec: dict, frame: pd.DataFrame) -> np.ndarray:
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    imp = spec["numeric_imputer_statistics"]
    kept = [spec["numeric_features"][i] for i, s in enumerate(imp) if s is not None]
    med = np.array([s for s in imp if s is not None], dtype=float)
    xn = frame.reindex(columns=kept).apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    xn = np.where(np.isnan(xn), med, xn)
    scaler = StandardScaler()
    scaler.mean_ = np.array(spec["numeric_scaler_mean"], dtype=float)
    scaler.scale_ = np.array(spec["numeric_scaler_scale"], dtype=float)
    scaler.var_ = scaler.scale_ ** 2
    scaler.n_features_in_ = len(kept)
    xn = scaler.transform(xn)
    cats = [list(c) for c in spec["onehot_categories"]]
    enc = OneHotEncoder(categories=cats, handle_unknown="ignore", sparse_output=False)
    enc.fit(pd.DataFrame({f: c for f, c in zip(spec["categorical_features"], cats)}))
    cat_df = frame.reindex(columns=spec["categorical_features"]).astype(object)
    for j, feat in enumerate(spec["categorical_features"]):
        col = cat_df[feat]
        cat_df[feat] = col.where(col.notna(), spec["categorical_imputer_statistics"][j])
    xc = enc.transform(cat_df)
    x = np.concatenate([xn, xc], axis=1)
    log_pred = x @ np.array(spec["coefficient"], dtype=float) + spec["intercept"]
    return np.maximum(np.exp(log_pred), 0.0)


def _random_frame(spec: dict, n: int = 5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {feat: rng.normal(100.0, 50.0, size=n) for feat in spec["numeric_features"]}
    land_cats = list(spec["onehot_categories"][0]) + ["out_of_train_range"]
    bld_cats = list(spec["onehot_categories"][1]) + ["missing"]
    data["land_area_bucket"] = [land_cats[i % len(land_cats)] for i in range(n)]
    data["building_area_bucket"] = [bld_cats[i % len(bld_cats)] for i in range(n)]
    frame = pd.DataFrame(data)
    frame.loc[0, spec["numeric_features"][3]] = np.nan  # exercise median imputation
    return frame


def test_coefficient_dimensions():
    pred = LinearJSONPredictor(_spec())
    assert len(pred.kept_numeric) == 86
    assert len(pred.coef) == 96
    assert len(pred.coef) == len(pred.kept_numeric) + sum(len(c) for c in pred.onehot_categories)


def test_linear_predictor_matches_sklearn_oracle():
    spec = _spec()
    frame = _random_frame(spec)
    got = LinearJSONPredictor(spec).predict(frame)
    expected = _sklearn_oracle(spec, frame)
    np.testing.assert_allclose(got, expected, rtol=1e-9, atol=1e-6)


def test_unknown_bucket_is_all_zero_onehot():
    spec = _spec()
    frame = _random_frame(spec)
    frame["land_area_bucket"] = "out_of_train_range"
    frame["building_area_bucket"] = "out_of_train_range"
    got = LinearJSONPredictor(spec).predict(frame)
    expected = _sklearn_oracle(spec, frame)
    np.testing.assert_allclose(got, expected, rtol=1e-9, atol=1e-6)


def test_load_predictors_linear_returns_two_linear():
    from house_fair_market_value.config import load_config
    from house_fair_market_value.predictors import load_predictors
    cfg = load_config(BASE)
    cfg = {**cfg, "backend": "linear"}
    tanah, bangunan = load_predictors(cfg, BASE)
    assert isinstance(tanah, LinearJSONPredictor)
    assert isinstance(bangunan, LinearJSONPredictor)


def test_catboost_predictor_runs_and_is_positive():
    pytest.importorskip("catboost")
    from house_fair_market_value.config import load_config
    from house_fair_market_value.predictors import CatBoostJSONPredictor
    cfg = load_config(BASE)
    model_path = BASE / cfg["models"]["catboost"]["tanah"]
    pred = CatBoostJSONPredictor.from_paths(model_path)
    frame = _random_frame(_spec())
    out = pred.predict(frame)
    assert out.shape == (len(frame),)
    assert (out >= 0).all()
