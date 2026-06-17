from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.capacity.logic import (
    dir_rate,
    kemampuan_bayar,
    penghasilan_bulanan,
)

client = TestClient(app)


def test_penghasilan_bulanan_adds_thr_and_bonus_monthly():
    # 10jt/bln + 12jt THR/12 (=1jt) + 24jt bonus/12 (=2jt) = 13jt
    assert penghasilan_bulanan(10_000_000, 12_000_000, 24_000_000) == 13_000_000


def test_dir_rate_tiers():
    assert dir_rate(14_999_999) == 0.5
    assert dir_rate(15_000_000) == 0.55   # boundary: not < 15M
    assert dir_rate(25_000_000) == 0.55   # boundary: <= 25M
    assert dir_rate(25_000_001) == 0.6


def test_kemampuan_bayar_uses_band_and_subtracts_angsuran():
    # penghasilan 20jt -> dir 0.55; (20jt - 0) * 0.55 = 11jt
    assert kemampuan_bayar(20_000_000, 0, 0, 0) == 11_000_000
    # subtract SLIK angsuran 2jt: (20jt - 2jt) * 0.55 = 9.9jt
    assert kemampuan_bayar(20_000_000, 0, 0, 2_000_000) == 9_900_000


def test_capacity_endpoint():
    resp = client.post(
        "/api/capacity",
        json={"gajiBulanan": 20_000_000, "thrTahunan": 0, "bonusTahunan": 0, "angsuranSlik": 0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["penghasilanBulanan"] == 20_000_000
    assert body["dirRate"] == 0.55
    assert body["kemampuanBayar"] == 11_000_000
