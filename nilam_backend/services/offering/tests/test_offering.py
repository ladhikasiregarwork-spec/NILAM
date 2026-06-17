from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.offering.logic import build_offering

client = TestClient(app)


def test_offering_unconstrained_all_ok():
    # requested 400jt; generous capacity & collateral -> every option finances fully
    out = build_offering(
        harga=500_000_000, uang_muka=100_000_000, usia=30,
        jangka_waktu=15, kemampuan=50_000_000, plafon_agunan=1_000_000_000,
    )
    assert out["maxTenorByAge"] == 25
    assert out["requested"] == 400_000_000
    assert len(out["schemes"]) > 0
    for scheme in out["schemes"]:
        assert len(scheme["tenorOptions"]) > 0
        for opt in scheme["tenorOptions"]:
            assert opt["tambahanDp"] == 0
            assert opt["ok"] is True
            assert len(opt["schedule"]) >= 1
            assert opt["angsuran"] == opt["schedule"][0]["angsuran"]


def test_offering_collateral_cap_forces_extra_dp():
    # collateral cap 100jt < requested 400jt -> needs >= 300jt extra DP, ok False
    out = build_offering(
        harga=500_000_000, uang_muka=100_000_000, usia=30,
        jangka_waktu=15, kemampuan=50_000_000, plafon_agunan=100_000_000,
    )
    opt = out["schemes"][0]["tenorOptions"][0]
    assert opt["tambahanDp"] >= 300_000_000
    assert opt["ok"] is False


def test_offering_filters_schemes_by_max_tenor_for_age():
    # usia 45 -> tenorMaks = min(25, 56-45) = 11; fixed3/fixed5 (minTenor 15) excluded
    out = build_offering(
        harga=500_000_000, uang_muka=100_000_000, usia=45,
        jangka_waktu=10, kemampuan=50_000_000, plafon_agunan=1_000_000_000,
    )
    assert out["maxTenorByAge"] == 11
    ids = {s["scheme"] for s in out["schemes"]}
    assert "fixed3" not in ids and "fixed5" not in ids
    assert "fixed1" in ids


def test_offering_endpoint():
    resp = client.post(
        "/api/offering",
        json={
            "harga": 500_000_000, "uangMuka": 100_000_000, "usia": 30,
            "jangkaWaktu": 15, "kemampuan": 50_000_000, "plafonAgunan": 1_000_000_000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["maxTenorByAge"] == 25
    assert len(body["schemes"]) > 0


def test_offering_usia_none_uses_cap_tenor():
    # usia omitted -> max_tenor_by_age returns the cap (25); response is valid, no crash
    out = build_offering(
        harga=500_000_000, uang_muka=100_000_000, usia=None,
        jangka_waktu=15, kemampuan=50_000_000, plafon_agunan=1_000_000_000,
    )
    assert out["maxTenorByAge"] == 25
    assert len(out["schemes"]) > 0
