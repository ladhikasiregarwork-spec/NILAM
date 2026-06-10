from __future__ import annotations

import numpy as np
import pandas as pd


def standardize_key(series: pd.Series) -> pd.Series:
    """Parity with src.inference_lookup._standardize_key."""
    return series.astype("string").str.strip().str.lower().str.replace(r"\s+", " ", regex=True)


def parse_appraisal_month(series: pd.Series) -> pd.Series:
    """Parity with src.preprocessing.parse_appraisal_month (YYYYMM -> first of month)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    text = series.astype("string").str.strip()
    digits = text.str.replace(r"\D+", "", regex=True)
    yyyymm = digits.where(digits.str.len().eq(6))
    parsed = pd.to_datetime(yyyymm + "01", format="%Y%m%d", errors="coerce")
    fallback = pd.to_datetime(text, errors="coerce")
    return parsed.fillna(fallback)


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def create_property_features(df: pd.DataFrame, land_col: str, building_col: str) -> pd.DataFrame:
    """Parity with src.feature_engineering.create_property_features(include_target=False)."""
    result = df.copy()
    result["log_land_area"] = np.log1p(result[land_col])
    result["log_building_area"] = np.log1p(result[building_col])
    result["building_to_land_ratio"] = _safe_divide(result[building_col], result[land_col])
    result["is_land_only"] = result[building_col].eq(0).astype(int)
    result["land_area_bucket"] = pd.NA
    result["building_area_bucket"] = pd.NA
    return result.replace([np.inf, -np.inf], np.nan)


def create_location_features(df: pd.DataFrame) -> pd.DataFrame:
    """Parity with src.feature_engineering.create_location_features."""
    result = df.copy()
    aliases = {
        "men": ["men", "sum_pria"],
        "women": ["women", "sum_wanita"],
        "total_family": ["total_family", "sum_jumlah_kk"],
        "credit_loan_total": ["credit_loan_total", "sum_pinjaman_loan"],
        "area_size": ["area_size", "sum_luas_wilayah", "shape_area"],
        "total_population": ["total_population", "sum_jumlah_penduduk"],
    }
    found = {key: next((c for c in cands if c in result.columns), None) for key, cands in aliases.items()}
    if found["total_population"] is None and found["men"] and found["women"]:
        result["total_population"] = (
            pd.to_numeric(result[found["men"]], errors="coerce")
            + pd.to_numeric(result[found["women"]], errors="coerce")
        )
        found["total_population"] = "total_population"
    specs = {
        "female_ratio": ("women", "total_population"),
        "male_ratio": ("men", "total_population"),
        "loan_per_family": ("credit_loan_total", "total_family"),
        "loan_per_capita": ("credit_loan_total", "total_population"),
        "population_density": ("total_population", "area_size"),
        "family_density": ("total_family", "area_size"),
    }
    for name, (num_key, den_key) in specs.items():
        num_col, den_col = found.get(num_key), found.get(den_key)
        if num_col and den_col:
            result[name] = _safe_divide(
                pd.to_numeric(result[num_col], errors="coerce"),
                pd.to_numeric(result[den_col], errors="coerce"),
            )
    return result.replace([np.inf, -np.inf], np.nan)


def create_time_features(df: pd.DataFrame, reference_min_month_index: int) -> pd.DataFrame:
    """Parity with src.feature_engineering.create_time_features (fixed reference)."""
    result = df.copy()
    date = pd.to_datetime(result["appraisal_date"], errors="coerce")
    result["appraisal_year"] = date.dt.year
    result["appraisal_month_num"] = date.dt.month
    result["month_index"] = result["appraisal_year"] * 12 + result["appraisal_month_num"]
    result["month_num_since_start"] = result["month_index"] - int(reference_min_month_index)
    return result


def apply_area_bucket_edges(df: pd.DataFrame, bucket_edges: dict, land_col: str, building_col: str) -> pd.DataFrame:
    """Parity with src.feature_engineering.apply_area_bucket_edges (identical pd.cut labels)."""
    result = df.copy()
    columns = {"land_area_bucket": land_col, "building_area_bucket": building_col}
    for bucket_col, source_col in columns.items():
        edges = bucket_edges.get(bucket_col, [])
        values = pd.to_numeric(result[source_col], errors="coerce")
        if len(edges) < 2:
            result[bucket_col] = "missing"
            continue
        result[bucket_col] = (
            pd.cut(values, bins=edges, include_lowest=True).astype("string").fillna("out_of_train_range")
        )
    return result


def enrich_with_location_lookup(df: pd.DataFrame, lookup: pd.DataFrame, keys: list[str]) -> tuple[pd.DataFrame, bool]:
    """Parity with src.inference_lookup.enrich_with_location_lookup; also returns whether a key matched."""
    result = df.copy()
    use_keys = [k for k in keys if k in result.columns and k in lookup.columns]
    if not use_keys:
        return result, False
    lk = lookup.copy()
    for key in use_keys:
        result[key] = standardize_key(result[key])
        lk[key] = standardize_key(lk[key])
    merged = result.merge(lk, how="left", on=use_keys, suffixes=("", "_lookup"))
    location_cols = [c for c in lk.columns if c not in use_keys]
    matched = bool(merged[location_cols].notna().any(axis=1).iloc[0]) if location_cols else False
    for col in location_cols:
        lookup_col = f"{col}_lookup"
        if lookup_col in merged.columns:
            merged[col] = merged[col].combine_first(merged[lookup_col]) if col in merged.columns else merged[lookup_col]
            merged = merged.drop(columns=[lookup_col])
    return merged, matched


def assemble_features(raw: dict, lookup: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, bool]:
    """Mirror src.predict order: enrich -> property -> location -> time -> buckets."""
    land_col = cfg.get("land_area_column", "luas_tanah")
    building_col = cfg.get("building_area_column", "luas_bangunan")
    month = raw.get("appraisal_month") or cfg["current_month"]
    df = pd.DataFrame([{
        land_col: float(raw["luas_tanah"]),
        building_col: float(raw["luas_bangunan"]),
        "kodepos_agunan": raw.get("kodepos_agunan"),
        "kelurahan_standardized": raw.get("kelurahan_standardized"),
        "appraisal_date": str(month),
    }])
    df["appraisal_date"] = parse_appraisal_month(df["appraisal_date"])
    df, matched = enrich_with_location_lookup(df, lookup, cfg["lookup_keys"])
    df = create_property_features(df, land_col, building_col)
    df = create_location_features(df)
    df = create_time_features(df, cfg["reference_min_month_index"])
    df = apply_area_bucket_edges(df, cfg["area_bucket_edges"], land_col, building_col)
    return df, matched
