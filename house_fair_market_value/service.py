from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import load_config
from .features import assemble_features
from .predictors import load_predictors


class FairValueService:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.cfg = load_config(self.base_dir)
        self.lookup = pd.read_parquet(self.base_dir / self.cfg["location_lookup_path"])
        self.tanah, self.bangunan = load_predictors(self.cfg, self.base_dir)

    def predict_one(self, request: dict) -> dict:
        luas_tanah = float(request["luas_tanah"])
        luas_bangunan = float(request["luas_bangunan"])
        raw = {
            "luas_tanah": luas_tanah,
            "luas_bangunan": luas_bangunan,
            "kodepos_agunan": request.get("kode_pos"),
            "kelurahan_standardized": request.get("kelurahan"),
            "appraisal_month": request.get("appraisal_month"),
        }
        df, matched = assemble_features(raw, self.lookup, self.cfg)
        land_value = float(self.tanah.predict(df)[0])
        building_value = 0.0 if luas_bangunan <= 0 else float(self.bangunan.predict(df)[0])
        warnings: list[str] = []
        if not matched:
            warnings.append(
                "Location not found in lookup; location features fell back to training "
                "medians. Provide a valid kode_pos and kelurahan for better accuracy."
            )
        return {
            "land_value": round(land_value, 2),
            "building_value": round(building_value, 2),
            "fair_value": round(land_value + building_value, 2),
            "location_matched": matched,
            "backend": self.cfg["backend"],
            "warnings": warnings,
        }
