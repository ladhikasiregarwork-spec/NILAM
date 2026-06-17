from nilam_backend.services.offering.kpr_math import (
    anuitas,
    build_schedule,
    max_plafond,
    max_tenor_by_age,
)


def test_zero_rate_paths():
    assert anuitas(12_000_000, 0.0, 12) == 1_000_000
    assert max_plafond(1_000_000, 0.0, 12) == 12_000_000


def test_anuitas_and_max_plafond_are_inverse_within_rounding():
    principal, rate, months = 500_000_000, 0.075, 240
    a = anuitas(principal, rate, months)
    back = max_plafond(a, rate, months)
    assert abs(back - principal) <= 50  # only rounding noise


def test_guards_return_zero():
    assert anuitas(0, 0.1, 12) == 0
    assert anuitas(1_000_000, 0.1, 0) == 0
    assert max_plafond(0, 0.1, 12) == 0
    assert max_plafond(1_000_000, 0.1, 0) == 0


def test_max_tenor_by_age():
    assert max_tenor_by_age(None) == 25
    assert max_tenor_by_age(40) == 16     # min(25, 56-40)
    assert max_tenor_by_age(20) == 25     # capped at 25
    assert max_tenor_by_age(55) == 1      # floored at 1


def test_build_schedule_fixed_then_floating():
    periods = [{"years": 1, "rate": 0.0175}, {"years": None, "rate": 0.125}]
    sched = build_schedule(100_000_000, 10, periods)
    assert len(sched) == 2
    assert sched[0]["fromYear"] == 1 and sched[0]["toYear"] == 1
    assert sched[0]["rate"] == 0.0175 and sched[0]["floating"] is False
    assert sched[1]["fromYear"] == 2 and sched[1]["toYear"] == 10
    assert sched[1]["floating"] is True
    # floating installment is higher than the promo installment
    assert sched[1]["angsuran"] > sched[0]["angsuran"]
