from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.decision.logic import build_decision

client = TestClient(app)


def test_affordable_high_score_approved():
    out = build_decision(kemampuan_bayar=11_000_000, angsuran_kpr=5_000_000, score=80, grade="A · Sangat Baik")
    assert out["decision"] == "approved"
    assert out["marginKemampuan"] == 6_000_000


def test_not_affordable_rejected_regardless_of_score():
    out = build_decision(kemampuan_bayar=5_000_000, angsuran_kpr=8_000_000, score=90, grade="A · Sangat Baik")
    assert out["decision"] == "rejected"
    assert out["marginKemampuan"] == -3_000_000


def test_affordable_mid_score_review():
    out = build_decision(kemampuan_bayar=10_000_000, angsuran_kpr=4_000_000, score=55, grade="C · Cukup")
    assert out["decision"] == "review"


def test_affordable_low_score_rejected():
    out = build_decision(kemampuan_bayar=10_000_000, angsuran_kpr=4_000_000, score=40, grade="D · Kurang")
    assert out["decision"] == "rejected"


def test_decision_endpoint():
    resp = client.post(
        "/api/decision",
        json={"kemampuanBayar": 11_000_000, "angsuranKpr": 5_000_000, "score": 70, "grade": "B · Baik"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["decision"] == "approved"
    assert body["marginKemampuan"] == 6_000_000
    assert isinstance(body["reasons"], list) and len(body["reasons"]) >= 1
