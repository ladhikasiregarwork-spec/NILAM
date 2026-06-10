# House Price Fair Value API

Estimates `fair_value = land_value + building_value` for a collateral property,
using the alternate **tanah** (land) and **bangunan** (building) models.

## Run

From the project root (`npw_using_loc/`):

```bash
pip install -r house_fair_market_value/requirements.txt
uvicorn house_fair_market_value.app:app --reload
```

## Endpoints

- `GET /health` → `{"status":"ok","backend":"linear"}`
- `POST /predict`

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"luas_tanah": 80, "luas_bangunan": 50, "kode_pos": "40123", "kelurahan": "antapani kidul"}'
```

Response:

```json
{"land_value": 0.0, "building_value": 0.0, "fair_value": 0.0,
 "location_matched": true, "backend": "linear", "warnings": []}
```

Only `luas_tanah` (> 0) and `luas_bangunan` (≥ 0) are required. `kode_pos` +
`kelurahan` pull ~84 location/demographic features from
`artifacts/location_feature_lookup.parquet`; on a miss those features fall back
to training medians and a warning is returned. `luas_bangunan = 0` is treated as
land-only (`building_value = 0`).

## Switching backend

Edit `model_config.json` → `"backend"`:
- `"linear"` (default): pure-NumPy from the linear-regression JSON exports; no ML libs at runtime.
- `"catboost"`: loads the CatBoost native-JSON models (needs the `catboost` package).

## Tests

```bash
python -m pytest house_fair_market_value/tests -v
```

22 tests: config, feature-parity vs the original `house_price_model/src`, the
NumPy linear predictor vs a real-sklearn oracle (rtol 1e-9), service combination,
and the HTTP endpoints. `sklearn` and `httpx` are test-only dependencies.

## Model quality caveat

The linear-regression models are weak (land test R² ≈ −0.27, median APE ≈ 38%).
For production accuracy switch the backend to `catboost` (R² ≈ 0.47–0.55). Location
statistics are 2022 snapshots used as static structural proxies.
