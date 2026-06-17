from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.services.coverage.logic import (
    analyze_ocr_coverage,
    month_from_key,
    month_range_between,
)

client = TestClient(app)


def test_month_from_key():
    assert month_from_key("2025-11") == {"key": "2025-11", "short": "Nov", "label": "Nov 2025"}


def test_range_between_inclusive_ascending():
    span = month_range_between("2025-11", "2026-01")
    assert [m["key"] for m in span] == ["2025-11", "2025-12", "2026-01"]


def test_empty_detected_is_complete_and_minimum_depends_on_min():
    out = analyze_ocr_coverage([], min_months=12)
    assert out["expected"] == [] and out["detected"] == []
    assert out["isComplete"] is True
    assert out["meetsMinimum"] is False
    assert out["rangeLabel"] == ""
    assert analyze_ocr_coverage([], min_months=0)["meetsMinimum"] is True


def test_interior_gap_flagged_and_unsorted_input_sorted():
    # Apr 2025 .. Mar 2026 with Nov 2025 absent -> Nov is the only interior gap.
    keys = [
        "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
        "2025-10", "2025-12", "2026-01", "2026-02", "2026-03",
    ]
    out = analyze_ocr_coverage(list(reversed(keys)), min_months=12)
    assert len(out["expected"]) == 12
    assert [m["key"] for m in out["missing"]] == ["2025-11"]
    assert out["isComplete"] is False
    assert out["meetsMinimum"] is True   # span length 12 >= 12
    assert out["rangeLabel"] == "Apr 2025 – Mar 2026"


def test_meets_minimum_false_when_span_too_short():
    out = analyze_ocr_coverage(["2026-01", "2026-02"], min_months=12)
    assert out["isComplete"] is True       # no interior gap
    assert out["meetsMinimum"] is False    # only a 2-month span


def test_coverage_endpoint():
    resp = client.post(
        "/api/validation/coverage",
        json={"detectedMonths": ["2026-01", "2026-03"], "minMonths": 12},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert [m["key"] for m in body["missing"]] == ["2026-02"]
    assert body["meetsMinimum"] is False
