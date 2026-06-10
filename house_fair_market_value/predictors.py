from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def _load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LinearJSONPredictor:
    """Reproduce a fitted sklearn_linear_pipeline_v1 in pure NumPy.

    Columns whose imputer statistic is null were all-NaN at fit time and dropped
    by SimpleImputer; only the kept columns align with the scaler and coefficients.
    """

    def __init__(self, spec: dict):
        self.numeric_features = spec["numeric_features"]
        self.categorical_features = spec["categorical_features"]
        imp = spec["numeric_imputer_statistics"]
        self.kept_idx = [i for i, s in enumerate(imp) if s is not None]
        self.kept_numeric = [self.numeric_features[i] for i in self.kept_idx]
        self.num_median = np.array([imp[i] for i in self.kept_idx], dtype=float)
        self.scaler_mean = np.array(spec["numeric_scaler_mean"], dtype=float)
        self.scaler_scale = np.array(spec["numeric_scaler_scale"], dtype=float)
        self.cat_impute = list(spec["categorical_imputer_statistics"])
        self.onehot_categories = [list(c) for c in spec["onehot_categories"]]
        self.coef = np.array(spec["coefficient"], dtype=float)
        self.intercept = float(spec["intercept"])
        n_oh = sum(len(c) for c in self.onehot_categories)
        assert len(self.kept_numeric) == self.scaler_mean.size == self.scaler_scale.size
        assert self.coef.size == len(self.kept_numeric) + n_oh

    @classmethod
    def from_path(cls, path: Path) -> "LinearJSONPredictor":
        return cls(_load_json(path))

    def _design_matrix(self, df: pd.DataFrame) -> np.ndarray:
        numeric = df.reindex(columns=self.kept_numeric).apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        numeric = np.where(np.isnan(numeric), self.num_median, numeric)
        numeric = (numeric - self.scaler_mean) / self.scaler_scale
        onehot_blocks = []
        for feat, cats, fill in zip(self.categorical_features, self.onehot_categories, self.cat_impute):
            col = df.reindex(columns=[feat])[feat].astype(object)
            col = col.where(col.notna(), fill)
            block = np.zeros((len(df), len(cats)), dtype=float)
            values = col.tolist()
            for row_i, value in enumerate(values):
                for col_i, category in enumerate(cats):
                    if str(value) == str(category):
                        block[row_i, col_i] = 1.0
                        break
            onehot_blocks.append(block)
        return np.concatenate([numeric, *onehot_blocks], axis=1)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        log_pred = self._design_matrix(df) @ self.coef + self.intercept
        return np.maximum(np.exp(log_pred), 0.0)


class CatBoostJSONPredictor:
    """Load a CatBoost native-JSON model and predict in log space."""

    def __init__(self, model_path: Path, numeric_features: list[str], categorical_features: list[str]):
        from catboost import CatBoostRegressor
        self.model = CatBoostRegressor()
        self.model.load_model(str(model_path), format="json")
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features

    @classmethod
    def from_paths(cls, model_path: Path) -> "CatBoostJSONPredictor":
        sidecar = Path(model_path).with_name(Path(model_path).stem + "_metadata.json")
        meta = _load_json(sidecar)["metadata"]
        return cls(Path(model_path), meta["numeric_features"], meta["categorical_features"])

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        features = self.numeric_features + self.categorical_features
        data = df.reindex(columns=features).copy()
        for col in self.numeric_features:
            data[col] = pd.to_numeric(data[col], errors="coerce")
        for col in self.categorical_features:
            data[col] = data[col].astype("string").fillna("missing")
        log_pred = self.model.predict(data)
        return np.maximum(np.exp(log_pred), 0.0)


def load_predictors(cfg: dict, base_dir: Path):
    """Return (tanah_predictor, bangunan_predictor) for the configured backend."""
    backend = cfg["backend"]
    paths = cfg["models"][backend]
    base = Path(base_dir)
    if backend == "linear":
        return (LinearJSONPredictor.from_path(base / paths["tanah"]),
                LinearJSONPredictor.from_path(base / paths["bangunan"]))
    if backend == "catboost":
        return (CatBoostJSONPredictor.from_paths(base / paths["tanah"]),
                CatBoostJSONPredictor.from_paths(base / paths["bangunan"]))
    raise ValueError(f"Unknown backend: {backend!r}")
