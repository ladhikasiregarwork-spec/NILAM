"""OCR month-coverage engine (pure). Port of `engines/ocr/coverage.ts`.

Turns the set of detected "YYYY-MM" months into a structured coverage report:
the contiguous span earliest->latest, the interior gaps, and whether the span
meets a minimum length (mutasi enforces >= 12 months; slip enforces none).
"""

from typing import List

# Indonesian short month names, index 0 = Januari (verbatim from coverage.ts).
ID_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]


def month_from_index(idx: int) -> dict:
    """Build a CoverageMonth from a zero-based absolute month index (year*12 + month0)."""
    year = idx // 12
    month0 = idx % 12
    short = ID_MONTHS[month0]
    key = "{}-{:02d}".format(year, month0 + 1)
    return {"key": key, "short": short, "label": "{} {}".format(short, year)}


def index_from_key(key: str) -> int:
    """Parse a "YYYY-MM" key into a zero-based absolute month index."""
    y, m = (int(x) for x in key.split("-"))
    return y * 12 + (m - 1)


def month_from_key(key: str) -> dict:
    return month_from_index(index_from_key(key))


def month_range(end_key: str, count: int) -> List[dict]:
    """`count` consecutive months ending at `end_key` (inclusive), ascending."""
    end = index_from_key(end_key)
    return [month_from_index(end - i) for i in range(count - 1, -1, -1)]


def month_range_between(start_key: str, end_key: str) -> List[dict]:
    """Every consecutive month from `start_key` to `end_key`, inclusive, ascending."""
    count = index_from_key(end_key) - index_from_key(start_key) + 1
    return month_range(end_key, count) if count > 0 else []


def analyze_ocr_coverage(detected_keys: List[str], min_months: int = 0) -> dict:
    """Analyse OCR month coverage across the customer's UPLOADED span.

    The expected window is the contiguous range earliest->latest detected month.
    Any month missing strictly BETWEEN the first and last uploaded month is an
    interior gap. `meetsMinimum` separately reports whether enough months exist.
    """
    detected = [month_from_key(k) for k in sorted(detected_keys)]

    if not detected:
        return {
            "expected": [],
            "detected": [],
            "missing": [],
            "isComplete": True,
            "meetsMinimum": min_months == 0,
            "rangeLabel": "",
        }

    span = month_range_between(detected[0]["key"], detected[-1]["key"])
    detected_set = {m["key"] for m in detected}
    missing = [m for m in span if m["key"] not in detected_set]

    return {
        "expected": span,
        "detected": detected,
        "missing": missing,
        "isComplete": len(missing) == 0,
        "meetsMinimum": len(span) >= min_months,
        "rangeLabel": "{} – {}".format(span[0]["label"], span[-1]["label"]),
    }
