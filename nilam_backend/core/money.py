import math


def js_round(x: float) -> int:
    """Round half toward +infinity, matching JavaScript's Math.round.

    Python's built-in round() uses banker's rounding (round-half-to-even),
    which diverges from the TS engines. floor(x + 0.5) reproduces Math.round
    for both positive and negative inputs (Math.round(-2.5) === -2,
    math.floor(-2.5 + 0.5) == -2).
    """
    return math.floor(x + 0.5)
