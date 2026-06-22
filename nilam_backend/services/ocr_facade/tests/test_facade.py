"""OCR facade — the unified-classifier compatibility surface the nilam-prototype
upload step calls. Upstream `post_files` is patched (no live ocr_* services);
fixtures (KTP/KK/SLIK) run for real. Asserts each endpoint emits exactly the shape
the matching BFF route in `app/api/ocr/*` parses.
"""

import nilam_backend.services.ocr_facade.router as facade
from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.core.http import UpstreamError

client = TestClient(app)

_PDF = ("dok.pdf", b"%PDF-x", "application/pdf")


def _patch_post_files(monkeypatch, fn):
    monkeypatch.setattr(facade, "post_files", fn)


# --- /classify-batch : raw passthrough of ocr_classifier's response ----------
def test_classify_batch_passthrough(monkeypatch):
    raw = {"results": [{"filename": "a.pdf", "document_type": "slip", "confidence": "high"}]}

    async def fake(url, files, **kw):
        assert url.endswith("/classify-batch")
        return raw

    _patch_post_files(monkeypatch, fake)
    resp = client.post("/classify-batch", files=[("files", _PDF)])
    assert resp.status_code == 200
    assert resp.json() == raw  # BFF reads .results[].document_type itself


# --- /extract-slip : {ok, records:[...]} -------------------------------------
def test_extract_slip_records(monkeypatch):
    async def fake(url, files, **kw):
        assert url.endswith("/parse")
        return {"summary": {"dokumen": [
            {"tanggal_periode": "25.01.2026", "gaji_pokok": 8_000_000,
             "tunjangan": 2_000_000, "potongan": 1_000_000, "sumber_file": "slip.pdf"},
        ]}}

    _patch_post_files(monkeypatch, fake)
    resp = client.post("/extract-slip", files=[("files", _PDF)])
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    rec = body["records"][0]
    assert rec["totalUpah"] == 10_000_000 and rec["thp"] == 9_000_000


# --- /extract-sk : {ok, fields, filename} ------------------------------------
def test_extract_sk_fields(monkeypatch):
    async def fake(url, files, **kw):
        return {"summary": {"dokumen": [
            {"nama_institusi": "PT Maju", "jabatan": "Manajer", "nama_pekerja": "BUDI",
             "sumber_file": "sk.pdf"},
        ]}}

    _patch_post_files(monkeypatch, fake)
    resp = client.post("/extract-sk", files={"file": _PDF})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["fields"]["perusahaan"] == "PT Maju"
    assert body["filename"] == "sk.pdf"


# --- /extract-mutasi : {ok, fields, filename} --------------------------------
def test_extract_mutasi_fields(monkeypatch):
    async def fake(url, files, **kw):
        assert url.endswith("/api/v1/mutations/extract-batch")
        return {
            "files": [{"filename": "mut.pdf", "account": {"no_rekening": "123"}, "transactions": []}],
            "credits": [{"tanggal": "25/01/26", "keterangan": "GAJI", "amount": 10_000_000,
                         "category": "Gaji"}],
            "audit": {"category_totals": {"Gaji": {"sum": 10_000_000, "min": 10_000_000}}},
        }

    _patch_post_files(monkeypatch, fake)
    resp = client.post("/extract-mutasi", files=[("files", _PDF)])
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["fields"]["totalKredit"] == 10_000_000
    assert body["fields"]["transactions"][0]["klasifikasi"] == "Gaji"
    assert body["filename"] == "mut.pdf"


# --- upstream failure degrades to 502 (best-effort BFF routes swallow it) -----
def test_extract_slip_upstream_error_502(monkeypatch):
    async def boom(url, files, **kw):
        raise UpstreamError("slip", "connect refused")

    _patch_post_files(monkeypatch, boom)
    resp = client.post("/extract-slip", files=[("files", _PDF)])
    assert resp.status_code == 502
    assert resp.json()["ok"] is False


# --- KTP/KK/SLIK fixtures (no upstream) ---------------------------------------
def test_extract_ktp_fixture():
    resp = client.post("/extract-ktp", params={"who": "pasangan"}, files={"file": _PDF})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["fields"]["nama"] == "SITI NURHALIZA"
    assert body["filename"] == "ktp_pasangan.pdf"


def test_extract_kk_fixture():
    resp = client.post("/extract-kk", files={"file": _PDF})
    assert resp.json()["fields"]["kepalaKeluarga"] == "BUDI SANTOSO"


def test_slik_fixture_and_missing_nik():
    ok_resp = client.get("/slik", params={"nik": "3201234567890002"})
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert body["ok"] is True
    assert body["namaDebitur"] == "BUDI SANTOSO"
    assert body["totalAngsuran"] == 3_500_000

    bad = client.get("/slik")
    assert bad.status_code == 400
    assert bad.json()["ok"] is False
