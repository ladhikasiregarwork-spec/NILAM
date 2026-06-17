from fastapi.testclient import TestClient

from nilam_backend.app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "nilam_backend"


def test_js_round_matches_math_round():
    from nilam_backend.core.money import js_round

    assert js_round(2.5) == 3
    assert js_round(2.4) == 2
    assert js_round(-2.5) == -2
    assert js_round(0.5) == 1
