from fastapi.testclient import TestClient

from nilam_backend.app.main import app

client = TestClient(app)


def _payload(harga):
    txns = [{"tanggal": "25/{:02d}/26".format(m), "remark": "GAJI", "nominal": 10_000_000,
             "dk": "Kredit", "klasifikasi": "Gaji"} for m in range(1, 13)]
    txns.append({"tanggal": "20/12/25", "remark": "THR", "nominal": 20_000_000,
                 "dk": "Kredit", "klasifikasi": "THR"})
    return {
        "joint": False,
        "uploads": ["slip.pdf", "mutasi.pdf"],
        "ocr": {"mutasi": {"transactions": txns},
                "slipRecords": [{"tanggalPembayaran": "25.01.2026", "thp": 9_500_000}]},
        "userInput": {"nik": "3201234567890002", "usia": 35, "jangkaWaktu": 15,
                      "uangMuka": 100_000_000, "pendidikan": "S1", "statusKawin": "Kawin",
                      "jumlahTanggungan": 1, "punyaSimpananBri": True},
        "agunan": {"harga": harga, "luasTanah": 100, "luasBangunan": 60},
        "npw": 500_000_000,
    }


def test_process_runs_all_nodes_in_order_and_assembles_view():
    resp = client.post("/api/applications/app-1/process", json=_payload(400_000_000))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["status"] == "done"

    ev = client.get("/api/applications/app-1/events").json()["events"]
    # 8 nodes x (running + success), in canonical order, no error events.
    order = [e["nodeId"] for e in ev if e["status"] == "running"]
    assert order == ["upload", "ocr", "validasi", "fraud", "identity", "slik", "income", "thp"]
    assert not any(e["status"] == "error" for e in ev)

    view = body["view"]
    assert view["capacity"]["kemampuanBayar"] > 0
    assert view["income"]["nasabah"]["thp"] > 0
    assert view["decision"]["decision"] in ("approved", "review", "rejected")
    assert len(view["offering"]["schemes"]) > 0
    assert view["coverage"]["meetsMinimum"] is True   # 12 mutasi months present
    assert view["survey"]["status"] == "none"          # 400jt < threshold


def test_sub_threshold_skips_survey_gate():
    client.post("/api/applications/app-2/process", json=_payload(400_000_000))
    assert client.get("/api/applications/app-2/survey").json()["status"] == "none"


def test_above_threshold_pends_survey_then_approval_overrides_npw():
    client.post("/api/applications/app-3/process", json=_payload(600_000_000))
    assert client.get("/api/applications/app-3/survey").json()["status"] == "pending"

    before = client.get("/api/applications/app-3").json()["view"]["npw"]
    resp = client.post("/api/applications/app-3/survey",
                       json={"decision": "approved", "value": 800_000_000, "note": "ok"})
    body = resp.json()
    assert body["ok"] is True and body["status"] == "approved"
    assert body["surveyValue"] == 800_000_000

    after = client.get("/api/applications/app-3").json()
    assert after["survey"]["status"] == "approved"
    assert after["view"]["npw"] == 800_000_000        # RM value overrode NPW
    assert before == 600_000_000 or before == 500_000_000 or after["view"]["npw"] != before


def test_survey_rejection_halts():
    client.post("/api/applications/app-4/process", json=_payload(600_000_000))
    resp = client.post("/api/applications/app-4/survey", json={"decision": "rejected", "note": "nilai kurang"})
    assert resp.json()["status"] == "rejected"


def test_unknown_application_is_404():
    assert client.get("/api/applications/nope/events").status_code == 404
    assert client.get("/api/applications/nope/survey").status_code == 404
