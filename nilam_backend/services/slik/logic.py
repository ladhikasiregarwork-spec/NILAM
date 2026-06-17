"""SLIK / credit bureau — FIXTURE service (backend_info.md §6).

No real bureau feed exists yet; this returns seeded SlikReports keyed by NIK.
`totalAngsuran` (sum of ACTIVE facilities' installments) feeds capacity (10) and
THP (9). Installment seeds mirror `data/slikFixtures.ts` (nasabah 3.5jt,
pasangan 4.9jt). An unknown NIK yields a clean empty report (graceful default).
"""

from typing import List

from nilam_backend.domain.slik import SlikLoan, SlikReport


def _report(nik: str, nama: str, loans: List[SlikLoan]) -> SlikReport:
    """Derive totals from the facility list so seeds stay self-consistent."""
    return SlikReport(
        nik=nik,
        namaDebitur=nama,
        loans=loans,
        totalAngsuran=sum(l.angsuran for l in loans if (l.aktif is None or l.aktif)),
        kolekTerburuk=max([l.kualitas for l in loans], default=1),
        totalFasilitas=len(loans),
    )


SLIK_SEED = {
    "3201234567890002": _report(
        "3201234567890002", "BUDI SANTOSO",
        [SlikLoan(jenis="KKB", lembaga="Bank BRI", plafon=200_000_000, baki=150_000_000,
                  angsuran=3_500_000, status="Lancar", kualitas=1, sukuBunga=8.25, aktif=True)],
    ),
    "3271234567890001": _report(
        "3271234567890001", "SITI NURHALIZA",
        [SlikLoan(jenis="KTA", lembaga="Bank BRI", plafon=100_000_000, baki=80_000_000,
                  angsuran=4_900_000, status="Lancar", kualitas=1, sukuBunga=12.0, aktif=True)],
    ),
}


def get_slik(nik: str) -> dict:
    """Seeded SlikReport for known NIKs; a clean empty report otherwise."""
    rep = SLIK_SEED.get(nik)
    if rep is not None:
        return rep.model_dump()
    return SlikReport(nik=nik).model_dump()
