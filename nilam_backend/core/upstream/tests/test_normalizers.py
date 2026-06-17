"""Normalizer tests against representative raw upstream payloads (no live services)."""

from nilam_backend.core.upstream.classifier import normalize_classify
from nilam_backend.core.upstream.match import normalize_match
from nilam_backend.core.upstream.mutasi import normalize_mutasi
from nilam_backend.core.upstream.npw import normalize_npw
from nilam_backend.core.upstream.sk import normalize_sk
from nilam_backend.core.upstream.slip import normalize_slip


def test_classify_maps_and_guards_unknown_label():
    raw = {"count": 2, "results": [
        {"filename": "a.pdf", "document_type": "ktp", "confidence": "high"},
        {"filename": "b.pdf", "document_type": "weird", "confidence": "low"},
    ]}
    out = normalize_classify(raw)
    assert out[0] == {"fileName": "a.pdf", "type": "ktp", "confidence": "high"}
    assert out[1]["type"] == "unknown"  # unrecognized label guarded


def test_mutasi_renames_credits_and_rebuilds_totals():
    raw = {
        "files": [{
            "filename": "mutasi.pdf",
            "account": {"bank": "BRI", "no_rekening": "1234567890"},
            "transactions": [
                {"tanggal": "10/01/26", "keterangan": "TARIK TUNAI", "amount": 500_000, "type": "DB"},
                {"tanggal": "25/01/26", "keterangan": "GAJI", "amount": 10_000_000, "type": "CR"},
            ],
        }],
        "credits": [
            {"tanggal": "25/01/26", "keterangan": "GAJI", "amount": 10_000_000, "type": "CR", "category": "Gaji"},
        ],
        "audit": {"category_totals": {"Gaji": {"count": 1, "sum": 10_000_000, "min": 10_000_000}}},
    }
    out = normalize_mutasi(raw)
    assert out["noRekening"] == "1234567890"
    # one classified credit (Kredit) + one debit row
    kredit = [t for t in out["transactions"] if t["dk"] == "Kredit"]
    debit = [t for t in out["transactions"] if t["dk"] == "Debit"]
    assert len(kredit) == 1 and kredit[0]["remark"] == "GAJI" and kredit[0]["klasifikasi"] == "Gaji"
    assert kredit[0]["nominal"] == 10_000_000
    assert len(debit) == 1 and debit[0]["klasifikasi"] == "Lainnya"
    assert out["totalKredit"] == 10_000_000 and out["totalDebet"] == 500_000
    assert out["ringkasan"] == {"Gaji": 10_000_000}
    assert out["gajiNominal"] == 10_000_000
    assert out["fileName"] == ["mutasi.pdf"]


def test_slip_maps_indonesian_doc_rows_and_derives_thp():
    raw = {"summary": {"dokumen": [{
        "sumber_file": "slip_jan.pdf",
        "tanggal_periode": "25.01.2026",
        "gaji_pokok": 8_000_000,
        "tunjangan": 2_000_000,
        "potongan": 1_500_000,
        "total_dibayar": 8_500_000,
    }]}}
    out = normalize_slip(raw)
    rec = out["records"][0]
    assert rec["tanggalPembayaran"] == "25.01.2026"
    assert rec["totalUpah"] == 10_000_000      # gaji_pokok + tunjangan
    assert rec["totalPotongan"] == 1_500_000
    assert rec["thp"] == 8_500_000             # gross - potongan
    assert "thr" not in rec                     # slip data gap: no thr/bonus


def test_sk_renames_and_rejects_when_no_doc():
    raw = {"needs_password": False, "summary": {"dokumen": [{
        "sumber_file": "sk.pdf", "nama_institusi": "PT Maju", "jabatan": "Manajer",
        "status_karyawan": "Karyawan Tetap", "masa_kerja": "5 tahun", "nik": "320...",
        "tanggal_mulai_kerja": "01/02/2021",
    }]}}
    out = normalize_sk(raw)
    assert out["perusahaan"] == "PT Maju" and out["jabatan"] == "Manajer"
    assert out["statusKepegawaian"] == "Karyawan Tetap" and out["masaKerja"] == "5 tahun"

    rejected = normalize_sk({"needs_password": False, "summary": {"dokumen": []}})
    assert rejected["rejected"] is True
    locked = normalize_sk({"needs_password": True, "summary": {"dokumen": []}})
    assert locked["needsPassword"] is True and locked["rejected"] is False


def test_match_flattens_pairs():
    raw = {"matches": [{
        "slip": {"source_file": "slip.pdf"},
        "credit": {"tanggal": "25/01/26", "amount": 10_000_000, "category": "Gaji"},
        "confidence": 0.9, "reason": "amount+date", "amount_diff_rp": 0,
        "amount_diff_pct": 0, "days_off": 1, "match_pattern": "X+1",
    }], "audit": {"matched_count": 1, "months_processed": ["01/26"]}}
    out = normalize_match(raw)
    assert out["matchedCount"] == 1 and out["monthsProcessed"] == ["01/26"]
    assert out["pairs"][0]["matchPattern"] == "X+1" and out["pairs"][0]["amount"] == 10_000_000


def test_npw_snake_to_camel():
    raw = {"land_value": 600_000_000, "building_value": 400_000_000, "fair_value": 1_000_000_000,
           "location_matched": True, "backend": "linear", "warnings": ["w1"]}
    out = normalize_npw(raw)
    assert out == {"fairValue": 1_000_000_000, "landValue": 600_000_000,
                   "buildingValue": 400_000_000, "locationMatched": True,
                   "backend": "linear", "warnings": ["w1"]}
