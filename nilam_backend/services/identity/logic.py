"""Identity (KTP / KK) — FIXTURE service (backend_info.md §2).

No KTP/KK extraction backend exists yet, so this returns seeded, contract-shaped
records. Real OCR-backed identity is deferred (design spec §10 out-of-scope).
The pasangan seed mirrors `data/ocrFixtures.ts` IDENTITY_PASANGAN.
"""

from nilam_backend.domain.documents import KkExtract, KkMember, KtpExtract

KTP_SEED = {
    "nasabah": KtpExtract(
        nik="3201234567890002",
        nama="BUDI SANTOSO",
        gender="Laki-laki",
        tempatLahir="Jakarta",
        tanggalLahir="08/11/1988",
        alamat="Jl. Merdeka No. 10, Jakarta",
        statusPerkawinan="Kawin",
        fileName="ktp_nasabah.pdf",
    ),
    "pasangan": KtpExtract(
        nik="3271234567890001",
        nama="SITI NURHALIZA",
        gender="Perempuan",
        tempatLahir="Bandung",
        tanggalLahir="12/05/1990",
        alamat="Jl. Merdeka No. 10, Jakarta",
        statusPerkawinan="Kawin",
        fileName="ktp_pasangan.pdf",
    ),
}

KK_SEED = KkExtract(
    nomorKK="3201234567890123",
    kepalaKeluarga="BUDI SANTOSO",
    alamat="Jl. Merdeka No. 10, Jakarta",
    members=[
        KkMember(nama="BUDI SANTOSO", hubungan="Kepala Keluarga", nik="3201234567890002"),
        KkMember(nama="SITI NURHALIZA", hubungan="Istri", nik="3271234567890001"),
        KkMember(nama="ANANDA PUTRA", hubungan="Anak"),
    ],
    fileName="kk.pdf",
)


def get_identity(doc_type: str, who: str = "nasabah") -> dict:
    """Seeded KtpExtract (by `who`) or KkExtract, by document type."""
    if doc_type == "kk":
        return KK_SEED.model_dump()
    ktp = KTP_SEED.get(who, KTP_SEED["nasabah"])
    return ktp.model_dump()
