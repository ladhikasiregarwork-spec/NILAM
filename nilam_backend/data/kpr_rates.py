from dataclasses import dataclass


@dataclass(frozen=True)
class KprScheme:
    id: str
    label: str
    rateLabel: str
    rate: float          # indicative rate used for the displayed installment
    minTenor: int
    maxTenor: int
    tiered: bool = False
    note: str = ""


KPR_SCHEMES: list[KprScheme] = [
    KprScheme("fixed1", "Fixed 1 Tahun", "1,75%", 0.0175, 5, 25, note="Fixed 1 thn, lalu counter rate"),
    KprScheme("fixed3", "Fixed 3 Tahun", "2,65%", 0.0265, 15, 25, note="Fixed 3 thn, lalu counter rate"),
    KprScheme("fixed5", "Fixed 5 Tahun", "3,40%", 0.034, 15, 25, note="Fixed 5 thn, lalu counter rate"),
    KprScheme(
        "berjenjang", "Berjenjang", "2,95% → bertahap", 0.0295, 10, 20, tiered=True,
        note="Thn 1-3: 2,95% · 4-6: 6,95% · 7+: 8,95% · lalu counter rate",
    ),
    KprScheme(
        "fixedall", "Fixed All Tenor", "7,25–8,00%", 0.0775, 1, 25,
        note="Fixed sepanjang tenor: 1-4 thn 7,25% · 5-10 thn 7,75% · 11-25 thn 8,00%",
    ),
]

FLOATING_RATE = 0.125


def scheme_rate(scheme: KprScheme, tenor_years: int) -> float:
    """Rate for the angsuran estimate, given a tenor (handles Fixed All Tenor tiers)."""
    if scheme.id == "fixedall":
        if tenor_years <= 4:
            return 0.0725
        if tenor_years <= 10:
            return 0.0775
        return 0.08
    return scheme.rate


def rate_plan(scheme: KprScheme, tenor_years: int, floating: float = FLOATING_RATE) -> list[dict]:
    """Full rate plan over the tenor: promo windows, then floating for the remainder."""
    sid = scheme.id
    if sid == "fixed1":
        return [{"years": 1, "rate": 0.0175}, {"years": None, "rate": floating}]
    if sid == "fixed3":
        return [{"years": 3, "rate": 0.0265}, {"years": None, "rate": floating}]
    if sid == "fixed5":
        return [{"years": 5, "rate": 0.034}, {"years": None, "rate": floating}]
    if sid == "berjenjang":
        return [
            {"years": 3, "rate": 0.0295},
            {"years": 3, "rate": 0.0695},
            {"years": 4, "rate": 0.0895},
            {"years": None, "rate": floating},
        ]
    if sid == "fixedall":
        return [{"years": None, "rate": scheme_rate(scheme, tenor_years)}]
    return [{"years": None, "rate": scheme.rate}]
