from nilam_backend.core.money import js_round


def penghasilan_bulanan(gaji_bulanan: float, thr_tahunan: float, bonus_tahunan: float) -> float:
    """Gross monthly income = gaji/bln + THR/12 + bonus/12."""
    return gaji_bulanan + thr_tahunan / 12 + bonus_tahunan / 12


def dir_rate(penghasilan: float) -> float:
    """Debt-to-Income ratio by monthly income band: <15jt 0.50 · 15-25jt 0.55 · >25jt 0.60."""
    if penghasilan < 15_000_000:
        return 0.5
    if penghasilan <= 25_000_000:
        return 0.55
    return 0.6


def kemampuan_bayar(
    gaji_bulanan: float, thr_tahunan: float, bonus_tahunan: float, slik_angsuran: float
) -> int:
    """(penghasilan - angsuran SLIK) * DIR, rounded."""
    penghasilan = penghasilan_bulanan(gaji_bulanan, thr_tahunan, bonus_tahunan)
    return js_round((penghasilan - slik_angsuran) * dir_rate(penghasilan))
