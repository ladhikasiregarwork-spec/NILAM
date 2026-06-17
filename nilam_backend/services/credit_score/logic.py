"""KPR credit score (0-100). Port of `engines/scoring/creditScore.ts`.

9 factors: pendidikan, status kawin, usia, simpanan BRI, jangka waktu,
% uang muka, jumlah tanggungan, rasio gaji/angsuran, rasio harga/plafond.
"""

from typing import Optional

from nilam_backend.core.money import js_round


def pendidikan_pts(p: Optional[str]) -> int:
    v = (p or "").upper()
    if v in ("S3", "S2"):
        return 10
    if v in ("S1", "D3"):
        return 8
    if v in ("SMA/SMK", "SMA"):
        return 6
    if v == "SMP":
        return 4
    if v == "SD":
        return 2
    return 3


def kawin_pts(s: Optional[str]) -> int:
    l = (s or "").lower()
    if "belum" in l:
        return 3
    if "cerai" in l:
        return 2
    if "kawin" in l:
        return 5
    return 2


def usia_pts(a: Optional[int]) -> int:
    if a is None:
        return 4
    if 30 <= a <= 45:
        return 10
    if 25 <= a < 30:
        return 8
    if 45 < a <= 52:
        return 7
    if 21 <= a < 25:
        return 5
    if 52 < a <= 56:
        return 4
    return 2


def tenor_pts(y: Optional[int]) -> int:
    if y is None:
        return 4
    if y <= 10:
        return 10
    if y <= 15:
        return 8
    if y <= 20:
        return 6
    return 4


def tanggungan_pts(n: Optional[int]) -> int:
    if n is None:
        return 6
    if n == 0:
        return 10
    if n <= 2:
        return 8
    if n <= 4:
        return 5
    return 2


def compute_credit_score(inp: "CreditScoreInput") -> dict:
    p_pts = pendidikan_pts(inp.pendidikan)
    k_pts = kawin_pts(inp.statusKawin)
    u_pts = usia_pts(inp.usia)
    bri_pts = 10 if inp.punyaSimpananBri else 0
    t_pts = tenor_pts(inp.jangkaWaktu)

    dp_ratio = (
        inp.uangMuka / inp.hargaRumah
        if (inp.hargaRumah and inp.uangMuka is not None and inp.hargaRumah > 0)
        else None
    )
    dp_pts = 4 if dp_ratio is None else js_round(max(0.0, min(1.0, dp_ratio / 0.3)) * 15)

    tg_pts = tanggungan_pts(inp.jumlahTanggungan)

    gi_ratio = (
        inp.incomeMonthly / inp.angsuranBulanan
        if (inp.incomeMonthly and inp.angsuranBulanan and inp.angsuranBulanan > 0)
        else None
    )
    if gi_ratio is None:
        gi_pts = 8
    elif gi_ratio >= 3:
        gi_pts = 20
    elif gi_ratio >= 2:
        gi_pts = 15
    elif gi_ratio >= 1.5:
        gi_pts = 10
    elif gi_ratio >= 1:
        gi_pts = 6
    else:
        gi_pts = 2

    hp_ratio = (
        inp.hargaRumah / inp.plafond
        if (inp.hargaRumah and inp.plafond and inp.plafond > 0)
        else None
    )
    if hp_ratio is None:
        hp_pts = 4
    elif hp_ratio >= 1.43:
        hp_pts = 10
    elif hp_ratio >= 1.25:
        hp_pts = 8
    elif hp_ratio >= 1.1:
        hp_pts = 5
    else:
        hp_pts = 3

    score = max(0, min(100, p_pts + k_pts + u_pts + bri_pts + t_pts + dp_pts + tg_pts + gi_pts + hp_pts))
    grade = (
        "A · Sangat Baik" if score >= 80
        else "B · Baik" if score >= 65
        else "C · Cukup" if score >= 50
        else "D · Kurang"
    )

    return {
        "score": score,
        "grade": grade,
        "factors": [
            {"label": "Pendidikan", "points": p_pts, "max": 10, "detail": inp.pendidikan or "—"},
            {"label": "Status Kawin", "points": k_pts, "max": 5, "detail": inp.statusKawin or "—"},
            {"label": "Usia", "points": u_pts, "max": 10, "detail": "{} th".format(inp.usia) if inp.usia is not None else "—"},
            {"label": "Simpanan BRI", "points": bri_pts, "max": 10, "detail": "Ya" if inp.punyaSimpananBri else "Tidak"},
            {"label": "Jangka Waktu", "points": t_pts, "max": 10, "detail": "{} th".format(inp.jangkaWaktu) if inp.jangkaWaktu is not None else "—"},
            {"label": "Uang Muka", "points": dp_pts, "max": 15, "detail": "{}%".format(js_round(dp_ratio * 100)) if dp_ratio is not None else "—"},
            {"label": "Tanggungan", "points": tg_pts, "max": 10, "detail": "{} org".format(inp.jumlahTanggungan) if inp.jumlahTanggungan is not None else "—"},
            {"label": "Gaji / Angsuran", "points": gi_pts, "max": 20, "detail": "{:.1f}×".format(gi_ratio) if gi_ratio is not None else "—"},
            {"label": "Harga / Plafond", "points": hp_pts, "max": 10, "detail": "{:.2f}×".format(hp_ratio) if hp_ratio is not None else "—"},
        ],
    }


# Imported at the bottom to avoid a circular import at module load.
from .models import CreditScoreInput  # noqa: E402
