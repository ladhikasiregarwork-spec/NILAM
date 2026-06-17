from nilam_backend.data.kpr_rates import (
    FLOATING_RATE,
    KPR_SCHEMES,
    rate_plan,
    scheme_rate,
)


def _scheme(scheme_id):
    return next(s for s in KPR_SCHEMES if s.id == scheme_id)


def test_schemes_present():
    ids = {s.id for s in KPR_SCHEMES}
    assert ids == {"fixed1", "fixed3", "fixed5", "berjenjang", "fixedall"}


def test_scheme_rate_fixedall_tiers():
    s = _scheme("fixedall")
    assert scheme_rate(s, 4) == 0.0725
    assert scheme_rate(s, 10) == 0.0775
    assert scheme_rate(s, 11) == 0.08
    # non-tiered scheme returns its indicative rate
    assert scheme_rate(_scheme("fixed1"), 10) == 0.0175


def test_rate_plan_fixed1_then_floating():
    plan = rate_plan(_scheme("fixed1"), 10)
    assert plan == [{"years": 1, "rate": 0.0175}, {"years": None, "rate": FLOATING_RATE}]


def test_rate_plan_berjenjang_three_windows_then_floating():
    plan = rate_plan(_scheme("berjenjang"), 20)
    assert plan == [
        {"years": 3, "rate": 0.0295},
        {"years": 3, "rate": 0.0695},
        {"years": 4, "rate": 0.0895},
        {"years": None, "rate": FLOATING_RATE},
    ]


def test_rate_plan_fixedall_single_window():
    plan = rate_plan(_scheme("fixedall"), 8)
    assert plan == [{"years": None, "rate": 0.0775}]
