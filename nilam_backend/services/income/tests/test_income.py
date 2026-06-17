from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.domain.documents import MutasiExtract
from nilam_backend.services.income.logic import aggregate_buckets, build_income

client = TestClient(app)


def _mutasi(rows):
    txns = [
        {"tanggal": t, "remark": "", "nominal": n, "dk": dk, "klasifikasi": k}
        for (t, n, dk, k) in rows
    ]
    return MutasiExtract(transactions=txns)


def test_aggregate_buckets_only_counts_classified_credits():
    m = _mutasi([
        ("25/01/26", 10_000_000, "Kredit", "Gaji"),
        ("25/02/26", 12_000_000, "Kredit", "Gaji"),
        ("10/01/26", 500_000, "Debit", "Lainnya"),   # debit ignored
        ("01/01/26", 9_000_000, "Kredit", "Lainnya"),  # unclassified ignored
        ("20/12/25", 20_000_000, "Kredit", "THR"),
    ])
    b = aggregate_buckets(m)
    assert b["Gaji"] == {"count": 2, "sum": 22_000_000, "min": 10_000_000}
    assert b["THR"]["count"] == 1 and b["THR"]["sum"] == 20_000_000
    assert b["Bonus"]["count"] == 0 and b["Insentif"]["count"] == 0


def test_thp_is_avg_components_minus_angsuran():
    m = _mutasi([
        ("25/01/26", 10_000_000, "Kredit", "Gaji"),
        ("25/02/26", 12_000_000, "Kredit", "Gaji"),  # avg gaji = 11jt
        ("20/12/25", 24_000_000, "Kredit", "THR"),   # avg thr = 24jt
    ])
    out = build_income(m, angsuran_slik=2_000_000)
    comps = {c["key"]: c for c in out["nasabah"]["components"]}
    assert comps["Gaji"]["avg"] == 11_000_000
    assert comps["THR"]["avg"] == 24_000_000
    assert comps["Bonus"]["avg"] == 0
    # gross = 11jt + 24jt + 0 + 0 = 35jt; thp = 35jt - 2jt = 33jt
    assert out["nasabah"]["thp"] == 33_000_000
    assert out["total"] == 33_000_000
    assert "pasangan" not in out


def test_joint_adds_pasangan_leg():
    n = _mutasi([("25/01/26", 10_000_000, "Kredit", "Gaji")])
    p = _mutasi([("25/01/26", 8_000_000, "Kredit", "Gaji")])
    out = build_income(n, 0, joint=True, pasangan_mutasi=p, pasangan_angsuran=1_000_000)
    assert out["nasabah"]["thp"] == 10_000_000
    assert out["pasangan"]["thp"] == 7_000_000
    assert out["total"] == 17_000_000


def test_income_endpoint():
    resp = client.post(
        "/api/income/thp",
        json={
            "mutasi": {"transactions": [
                {"tanggal": "25/01/26", "nominal": 10_000_000, "dk": "Kredit", "klasifikasi": "Gaji"},
            ]},
            "angsuranSlik": 1_000_000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["nasabah"]["thp"] == 9_000_000
    assert body["total"] == 9_000_000
