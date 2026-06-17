from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.identity.logic import get_identity

client = TestClient(app)


def test_ktp_nasabah_and_pasangan_differ():
    nasabah = get_identity("ktp", "nasabah")
    pasangan = get_identity("ktp", "pasangan")
    assert nasabah["nik"] == "3201234567890002"
    assert pasangan["nik"] == "3271234567890001"
    assert pasangan["nama"] == "SITI NURHALIZA"


def test_kk_returns_members():
    kk = get_identity("kk")
    assert kk["kepalaKeluarga"] == "BUDI SANTOSO"
    assert len(kk["members"]) == 3
    assert kk["members"][1]["hubungan"] == "Istri"


def test_unknown_who_falls_back_to_nasabah():
    assert get_identity("ktp", "tetangga")["nik"] == "3201234567890002"


def test_identitas_endpoint():
    resp = client.post("/api/ocr/identitas", params={"type": "ktp", "who": "pasangan"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["type"] == "ktp"
    assert body["extract"]["nama"] == "SITI NURHALIZA"
