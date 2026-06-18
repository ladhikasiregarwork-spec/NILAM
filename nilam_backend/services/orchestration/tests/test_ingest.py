"""Raw-bundle ingestion (orchestrator owns OCR): classify -> route -> extract ->
NPW -> ProcessRequest, with the real `core/upstream/*` clients patched (no live
services), mirroring the design's "upstream calls patched" test approach (§8).
"""

import asyncio
import json

from fastapi.testclient import TestClient

import nilam_backend.services.orchestration.ingest as ingest
from nilam_backend.app.main import app
from nilam_backend.core.http import UpstreamError

client = TestClient(app)


def _run(coro):
    return asyncio.run(coro)


def _uploads():
    return [
        ("ktp.pdf", b"%PDF-ktp", "application/pdf"),
        ("slip_jan.pdf", b"%PDF-slip", "application/pdf"),
        ("mutasi.pdf", b"%PDF-mut", "application/pdf"),
        ("sk.pdf", b"%PDF-sk", "application/pdf"),
    ]


def _meta(harga=400_000_000):
    return {
        "joint": False,
        "userInput": {
            "nik": "3201234567890002", "usia": 35, "jangkaWaktu": 15,
            "uangMuka": 100_000_000, "pendidikan": "S1", "statusKawin": "Kawin",
            "jumlahTanggungan": 1, "punyaSimpananBri": True,
        },
        "agunan": {"harga": harga, "luasTanah": 100, "luasBangunan": 60,
                   "kelurahan": "Sukamaju", "kodepos": "12345"},
        "agunanKlas": {"kategori": "baru", "tier": "tier1", "prop": "tapak", "ukuran": "gt70"},
    }


_LABEL_OF = {"ktp.pdf": "ktp", "slip_jan.pdf": "slip", "mutasi.pdf": "mutasi", "sk.pdf": "sk"}


def _patch(monkeypatch, **over):
    async def classify(files):
        # `files` is the httpx multipart list: [(field, (name, content, ctype)), ...].
        names = [f[1][0] for f in files]
        return [{"fileName": n, "type": _LABEL_OF.get(n, "unknown"), "confidence": "high"} for n in names]

    async def slip(files, password=None):
        return {"records": [{"tanggalPembayaran": "25.01.2026", "totalUpah": 10_000_000,
                             "totalPotongan": 1_000_000, "thp": 9_000_000}]}

    async def mutasi(files):
        txns = [{"tanggal": "25/{:02d}/26".format(m), "remark": "GAJI", "nominal": 10_000_000,
                 "dk": "Kredit", "klasifikasi": "Gaji"} for m in range(1, 13)]
        return {"transactions": txns, "count": 12, "totalKredit": 120_000_000}

    async def sk(files, password=None):
        return {"perusahaan": "PT Maju", "jabatan": "Manajer"}

    async def npw(luas_tanah, luas_bangunan=None, kode_pos=None, kelurahan=None):
        return {"fairValue": 600_000_000, "landValue": 400_000_000}

    monkeypatch.setattr(ingest, "fetch_classify", over.get("classify", classify))
    monkeypatch.setattr(ingest, "fetch_slip", over.get("slip", slip))
    monkeypatch.setattr(ingest, "fetch_mutasi", over.get("mutasi", mutasi))
    monkeypatch.setattr(ingest, "fetch_sk", over.get("sk", sk))
    monkeypatch.setattr(ingest, "fetch_npw", over.get("npw", npw))


def test_ingest_classifies_routes_and_builds_process_request(monkeypatch):
    _patch(monkeypatch)
    req, audit = _run(ingest.ingest_bundle(_uploads(), _meta()))

    assert {t.klasifikasi for t in req.ocr.mutasi.transactions} == {"Gaji"}
    assert len(req.ocr.mutasi.transactions) == 12
    assert len(req.ocr.slipRecords) == 1 and req.ocr.slipRecords[0].thp == 9_000_000
    assert req.npw == 600_000_000
    assert req.userInput.nik == "3201234567890002"
    assert req.agunan.harga == 400_000_000
    assert req.agunanKlas.tier == "tier1"
    assert not audit.get("errors")          # no upstream failures


def test_ingest_degrades_when_mutasi_upstream_fails(monkeypatch):
    async def boom(files):
        raise UpstreamError("mutasi", "connection refused")

    _patch(monkeypatch, mutasi=boom)
    req, audit = _run(ingest.ingest_bundle(_uploads(), _meta()))

    assert req.ocr.mutasi.transactions == []                 # degraded to empty
    assert any("mutasi" in e for e in audit["errors"])       # recorded, not raised
    assert len(req.ocr.slipRecords) == 1                     # other stages unaffected


def test_ingest_skips_npw_without_luas_tanah(monkeypatch):
    _patch(monkeypatch)
    meta = _meta()
    meta["agunan"]["luasTanah"] = 0
    req, _audit = _run(ingest.ingest_bundle(_uploads(), meta))
    assert req.npw == 0


def test_process_bundle_endpoint_runs_pipeline(monkeypatch):
    _patch(monkeypatch)
    files = [("files", (n, c, ct)) for (n, c, ct) in _uploads()]
    resp = client.post(
        "/api/applications/bundle-1/process-bundle",
        data={"meta": json.dumps(_meta())},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["status"] == "done"
    assert body["view"]["income"]["nasabah"]["thp"] > 0
    assert body["view"]["decision"]["decision"] in ("approved", "review", "rejected")
    assert body["view"]["coverage"]["meetsMinimum"] is True   # 12 mutasi months
    # events are queryable just like the JSON /process route
    ev = client.get("/api/applications/bundle-1/events").json()["events"]
    assert [e["nodeId"] for e in ev if e["status"] == "running"][0] == "upload"
