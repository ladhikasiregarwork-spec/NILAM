from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.credit_score.logic import compute_credit_score, usia_pts
from nilam_backend.services.credit_score.models import CreditScoreInput

client = TestClient(app)


def test_factor_band_boundaries():
    assert usia_pts(None) == 4
    assert usia_pts(30) == 10 and usia_pts(45) == 10
    assert usia_pts(29) == 8
    assert usia_pts(46) == 7
    assert usia_pts(20) == 2


def test_strong_profile_scores_a():
    inp = CreditScoreInput(
        pendidikan="S1", statusKawin="Kawin", usia=35, punyaSimpananBri=True,
        jangkaWaktu=10, hargaRumah=500_000_000, uangMuka=150_000_000,
        jumlahTanggungan=0, incomeMonthly=20_000_000, angsuranBulanan=5_000_000,
        plafond=350_000_000,
    )
    out = compute_credit_score(inp)
    # 8 + 5 + 10 + 10 + 10 + 15 + 10 + 20 + 8 = 96
    assert out["score"] == 96
    assert out["grade"] == "A · Sangat Baik"
    by_label = {f["label"]: f for f in out["factors"]}
    assert by_label["Uang Muka"]["detail"] == "30%"
    assert by_label["Gaji / Angsuran"]["points"] == 20
    assert by_label["Harga / Plafond"]["points"] == 8   # 1.43x just under threshold
    assert sum(f["max"] for f in out["factors"]) == 100


def test_empty_input_falls_to_defaults_grade_d():
    out = compute_credit_score(CreditScoreInput())
    # 3 + 2 + 4 + 0 + 4 + 4 + 6 + 8 + 4 = 35
    assert out["score"] == 35
    assert out["grade"] == "D · Kurang"


def test_credit_score_endpoint():
    resp = client.post("/api/credit-score", json={"pendidikan": "S2", "usia": 35, "punyaSimpananBri": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert 0 <= body["score"] <= 100
    assert len(body["factors"]) == 9
