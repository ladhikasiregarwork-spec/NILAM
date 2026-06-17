from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.domain.documents import MutasiExtract, SlipGajiExtract
from nilam_backend.projection.matching import build_match

client = TestClient(app)


def test_only_credit_income_txns_kept_and_sorted():
    m = MutasiExtract(transactions=[
        {"tanggal": "25/02/26", "remark": "GAJI FEB", "nominal": 12_000_000, "dk": "Kredit", "klasifikasi": "Gaji"},
        {"tanggal": "25/01/26", "remark": "GAJI JAN", "nominal": 10_000_000, "dk": "Kredit", "klasifikasi": "Gaji"},
        {"tanggal": "10/01/26", "remark": "TARIK TUNAI", "nominal": 500_000, "dk": "Debit", "klasifikasi": "Lainnya"},
        {"tanggal": "01/01/26", "remark": "TRANSFER", "nominal": 9_000_000, "dk": "Kredit", "klasifikasi": "Lainnya"},
        {"tanggal": "20/12/25", "remark": "THR", "nominal": 20_000_000, "dk": "Kredit", "klasifikasi": "THR"},
    ])
    res = build_match(m, None)
    # debit + unclassified credit dropped; 3 income txns; ascending by date
    assert [t["tanggal"] for t in res["txns"]] == ["20/12/25", "25/01/26", "25/02/26"]
    assert res["txns"][0]["thr"] == 20_000_000 and res["txns"][0]["gaji"] == 0


def test_monthly_recap_aggregates_mutasi_and_slip():
    m = MutasiExtract(transactions=[
        {"tanggal": "25/01/26", "remark": "GAJI", "nominal": 10_000_000, "dk": "Kredit", "klasifikasi": "Gaji"},
    ])
    slip = SlipGajiExtract(records=[{
        "tanggalPembayaran": "25.01.2026",
        "totalUpah": 12_000_000,
        "totalPotongan": 2_500_000,
        "thp": 9_500_000,
        "potonganCuti": 500_000,
    }])
    res = build_match(m, slip)
    assert len(res["recaps"]) == 1
    r = res["recaps"][0]
    assert r["key"] == "01/26" and r["bulan"] == "Jan 2026"
    assert r["gajiMutasi"] == 10_000_000
    assert r["gajiSlip"] == 9_500_000        # THP -> gajiSlip
    assert r["incomeSlip"] == 12_000_000
    assert r["potonganSlip"] == 2_500_000
    assert r["potonganNet"] == 2_000_000      # 2.5jt - 0.5jt cuti
    assert r["tglBayarSlip"] == "25.01.2026"


def test_named_month_slip_key():
    slip = SlipGajiExtract(records=[{"tanggalPembayaran": "Mei 2026", "thp": 8_000_000}])
    res = build_match(None, slip)
    assert res["recaps"][0]["key"] == "05/26"
    assert res["recaps"][0]["bulan"] == "Mei 2026"


def test_matching_endpoint():
    resp = client.post(
        "/api/matching",
        json={
            "mutasi": {"transactions": [
                {"tanggal": "25/01/26", "remark": "GAJI", "nominal": 10_000_000, "dk": "Kredit", "klasifikasi": "Gaji"},
            ]},
            "slipRecords": [{"tanggalPembayaran": "25.01.2026", "thp": 9_500_000}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["incomeTransactions"]) == 1
    assert body["monthlyRecap"][0]["gajiSlip"] == 9_500_000
