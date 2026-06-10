from fastapi.testclient import TestClient

from house_fair_market_value.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["backend"] in {"linear", "catboost"}


def test_predict_ok():
    resp = client.post("/predict", json={"luas_tanah": 80.0, "luas_bangunan": 50.0})
    assert resp.status_code == 200
    body = resp.json()
    for key in ["land_value", "building_value", "fair_value", "location_matched", "backend", "warnings"]:
        assert key in body
    assert body["fair_value"] == round(body["land_value"] + body["building_value"], 2)


def test_predict_rejects_zero_land():
    resp = client.post("/predict", json={"luas_tanah": 0.0, "luas_bangunan": 50.0})
    assert resp.status_code == 422  # pydantic gt=0 validation
