from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.slik.logic import get_slik

client = TestClient(app)


def test_seeded_report_derives_totals():
    rep = get_slik("3201234567890002")
    assert rep["namaDebitur"] == "BUDI SANTOSO"
    assert rep["totalAngsuran"] == 3_500_000
    assert rep["totalFasilitas"] == 1
    assert rep["kolekTerburuk"] == 1


def test_pasangan_seed():
    assert get_slik("3271234567890001")["totalAngsuran"] == 4_900_000


def test_unknown_nik_is_clean_empty_report():
    rep = get_slik("0000000000000000")
    assert rep["loans"] == []
    assert rep["totalAngsuran"] == 0
    assert rep["totalFasilitas"] == 0


def test_slik_endpoint_ok():
    resp = client.get("/api/slik", params={"nik": "3201234567890002"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["report"]["totalAngsuran"] == 3_500_000


def test_slik_endpoint_missing_nik_is_400():
    resp = client.get("/api/slik")
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "nik wajib diisi"
