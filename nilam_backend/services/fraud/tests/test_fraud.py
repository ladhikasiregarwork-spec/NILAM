from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.fraud.logic import detect_fraud

client = TestClient(app)


def test_stub_returns_four_checks_and_overall():
    out = detect_fraud()
    assert [c["name"] for c in out["checks"]] == [
        "Slip Gaji Authentic", "Mutasi Valid (12 Bulan)", "Consistency Check", "Pattern Analysis",
    ]
    assert all(0 <= c["score"] <= 1 for c in out["checks"])
    assert out["overall"] == 0.94


def test_fraud_endpoint_ignores_inputs():
    resp = client.post("/api/fraud", json={"slip": {"x": 1}, "mutasi": None, "identity": {"nik": "123"}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["overall"] == 0.94
    assert len(body["checks"]) == 4
