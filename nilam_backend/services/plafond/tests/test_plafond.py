from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.data.ltv_grid import ltv_baru, ltv_lama, range_harga
from nilam_backend.domain.agunan import AgunanKlasifikasi
from nilam_backend.services.plafond.logic import build_plafond

client = TestClient(app)


def test_ltv_baru_grid_values():
    assert ltv_baru("tier1", "tapak", "gt70") == 0.95
    assert ltv_baru("tier3", "ruko", "gt70") == 0.75
    assert ltv_baru("local_champion", "apartemen", "mid") == 0.85


def test_ltv_lama():
    assert ltv_lama("refinancing") == 0.7
    assert ltv_lama("secondary", 4_000_000_000) == 0.9   # < 5M
    assert ltv_lama("secondary", 6_000_000_000) == 0.85  # 5-15M
    assert ltv_lama("secondary", 16_000_000_000) == 0.8  # > 15M


def test_range_harga_default_mid_when_missing():
    assert range_harga(None) == "mid"


def test_build_plafond_baru_with_extra_dp():
    klas = AgunanKlasifikasi(kategori="baru", tier="tier1", prop="tapak", ukuran="gt70")
    out = build_plafond(npw=1_000_000_000, harga=1_200_000_000, uang_muka=200_000_000, klas=klas)
    assert out["ltv"] == 0.95
    assert out["plafonAgunan"] == 950_000_000      # round(1B * 0.95)
    assert out["kebutuhan"] == 1_000_000_000        # 1.2B - 0.2B
    assert out["penambahanDp"] == 50_000_000        # 1.0B - 0.95B


def test_plafond_endpoint():
    resp = client.post(
        "/api/agunan/plafond",
        json={
            "npw": 1_000_000_000,
            "harga": 1_200_000_000,
            "uangMuka": 200_000_000,
            "klasifikasi": {"kategori": "baru", "tier": "tier1", "prop": "tapak", "ukuran": "gt70"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["plafonAgunan"] == 950_000_000
    assert body["penambahanDp"] == 50_000_000
