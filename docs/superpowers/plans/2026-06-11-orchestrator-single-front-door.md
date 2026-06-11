# Orchestrator Single Front Door — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ocr_match` the single front door for slip + mutasi extraction *and* matching, then rewire `ocr_orchestrator` to parse nothing itself — it sources slips, all-category credits, account/files, and the match result from one `ocr_match` call.

**Architecture:** Phase 1 extends `ocr_match` to pass through the two upstream response bodies (`slip_extraction`, `mutasi_extraction`) verbatim alongside the existing match result, and stops the `Gaji`-only filter from hiding the other categories. Phase 2 deletes the orchestrator's own `ocr_slip`/`ocr_mutasi` calls, replaces the in-process matcher import with an HTTP `match_documents` call (new `acquire` stage), and degrades to no-income (job still completes) when `ocr_match` is unreachable (decision D1). No `ocr_match` imports remain under `ocr_orchestrator/`.

**Tech Stack:** Python 3.12, FastAPI, `pydantic` / `pydantic-settings`, `httpx` (async), `pytest` + `unittest.IsolatedAsyncioTestCase`. Run everything from the **repo root** with `.venv\Scripts\python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-11-orchestrator-remote-match-design.md`

**Field naming (locked):** the two passthrough blocks are named `slip_extraction` and `mutasi_extraction`, each carrying the verbatim upstream response body (`{"documents": [...]}` and `{"files": [...], "credits": [...], "audit": {...}}` respectively).

---

## Sequencing & key facts

- **Phase 1 must ship before Phase 2** — Phase 2 reads fields Phase 1 adds.
- `ocr_match` currently has **no pytest suite**; Phase 1 creates `ocr_match/tests/`.
- The tracked stage `verify` is **renamed to `acquire`**. This touches
  `ocr_orchestrator/jobs.py` (`_DEFAULT_STAGES`) and `tests/test_jobs.py`.
- The orchestrator module `verify.py` is **renamed to `matching.py`**; its test
  `test_verify.py` → `test_matching.py`.
- **Known consequence of D1 + single front door:** `ocr_match/api.py` returns 400
  unless *both* a slip and a mutasi PDF are present. A slips-only or mutasi-only
  bundle therefore yields no income (degraded). The acquire stage guards this
  explicitly with a clear warning rather than firing a doomed request. This is an
  accepted regression of the single-front-door design.

---

# PHASE 1 — Extend `ocr_match` to pass through full extractions

### Task 1.1: Add `slip_extraction` / `mutasi_extraction` to `MatchResponse`

**Files:**
- Modify: `ocr_match/models.py`

- [ ] **Step 1: Add the two passthrough fields**

In `ocr_match/models.py`, add `Any` to the typing import and extend `MatchResponse`.

Change the import line near the top:

```python
from typing import Any, Optional
```

Replace the `MatchResponse` class (currently lines 88–92) with:

```python
class MatchResponse(BaseModel):
    matches: list[MatchPair]
    unmatched_slips: list[ParsedSlip]
    unmatched_credits: list[GajiCredit]
    audit: MatchAudit
    # Verbatim upstream response bodies, passed through so a single caller (the
    # orchestrator) can source full slip + mutasi extraction from one match call.
    # slip_extraction == ocr_slip /parse body: {"documents": [...]}
    # mutasi_extraction == ocr_mutasi extract-batch body:
    #   {"files": [...], "credits": [...all categories...], "audit": {...}}
    slip_extraction: dict[str, Any] = Field(default_factory=dict)
    mutasi_extraction: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 2: Sanity-check the import compiles**

Run: `.venv\Scripts\python -c "import ocr_match.models; print('ok')"`
Expected: prints `ok` (no ImportError).

- [ ] **Step 3: Commit**

```bash
git add ocr_match/models.py
git commit -m "feat(ocr_match): add slip_extraction/mutasi_extraction passthrough fields"
```

---

### Task 1.2: Return the raw upstream payloads from `ocr_match/upstream.py`

The two clients keep their typed return (used by the matcher) **and** return the
full raw payload (for passthrough). The mutasi raw payload keeps **all** categories;
only the matcher's `credits` list stays `Gaji`-filtered.

**Files:**
- Modify: `ocr_match/upstream.py`
- Test: `ocr_match/tests/test_upstream_passthrough.py` (create)

- [ ] **Step 1: Create the test package + failing test**

Create `ocr_match/tests/__init__.py` (empty file):

```python
```

Create `ocr_match/tests/test_upstream_passthrough.py`:

```python
import unittest
from unittest import mock

from ocr_match import upstream


class _FakeResp:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, files=None, data=None, params=None):
        return self._resp


def _patch_client(resp):
    return mock.patch.object(upstream.httpx, "AsyncClient",
                             lambda *a, **k: _FakeClient(resp))


class TestPassthrough(unittest.IsolatedAsyncioTestCase):
    async def test_parse_slips_returns_typed_and_raw(self):
        body = {"documents": [{"source_file": "s.pdf", "total_paid": 1.0}]}
        with _patch_client(_FakeResp(200, body)):
            slips, raw = await upstream.parse_slips([("s.pdf", b"x")])
        self.assertEqual(len(slips), 1)
        self.assertEqual(slips[0].source_file, "s.pdf")
        self.assertEqual(raw, body)

    async def test_extract_mutations_filters_typed_but_keeps_all_in_raw(self):
        body = {
            "files": [{"filename": "m.pdf", "account": {"nama": "BUDI"}}],
            "credits": [
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "GAJI",
                 "amount": 9.0, "page": 1, "category": "Gaji"},
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "THR",
                 "amount": 5.0, "page": 1, "category": "THR"},
            ],
            "audit": {},
        }
        with _patch_client(_FakeResp(200, body)):
            credits, raw = await upstream.extract_mutations([("m.pdf", b"x")])
        # typed list is Gaji-only (used by the matcher)...
        self.assertEqual([c.category for c in credits], ["Gaji"])
        # ...but the raw passthrough keeps every category.
        self.assertEqual([c["category"] for c in raw["credits"]], ["Gaji", "THR"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_match/tests/test_upstream_passthrough.py -v`
Expected: FAIL — `parse_slips`/`extract_mutations` currently return a plain list, so
the tuple-unpack `slips, raw = ...` raises `ValueError` / `TypeError`.

- [ ] **Step 3: Change `parse_slips` to return `(list, raw)`**

In `ocr_match/upstream.py`, replace the end of `parse_slips` (currently lines 74–76):

```python
    payload = r.json()
    docs = payload.get("documents", [])
    return [ParsedSlip(**d) for d in docs], payload
```

And update its signature/return annotation (line 39–42 area):

```python
async def parse_slips(
    pdfs: list[tuple[str, bytes]],
    password: str | None = None,
) -> tuple[list[ParsedSlip], dict]:
```

- [ ] **Step 4: Change `extract_mutations` to return `(gaji_list, raw)`**

Replace the end of `extract_mutations` (currently lines 117–119):

```python
    payload = r.json()
    credits = payload.get("credits", [])
    gaji = [GajiCredit(**c) for c in credits if c.get("category") == "Gaji"]
    return gaji, payload
```

And update its signature/return annotation (line 81–84 area):

```python
async def extract_mutations(
    pdfs: list[tuple[str, bytes]],
    password: str | None = None,
) -> tuple[list[GajiCredit], dict]:
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_match/tests/test_upstream_passthrough.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add ocr_match/upstream.py ocr_match/tests/__init__.py ocr_match/tests/test_upstream_passthrough.py
git commit -m "feat(ocr_match): return raw upstream payloads alongside typed lists"
```

---

### Task 1.3: Populate the passthrough blocks in `ocr_match/pipeline.py`

**Files:**
- Modify: `ocr_match/pipeline.py`
- Test: `ocr_match/tests/test_pipeline_passthrough.py` (create)

- [ ] **Step 1: Write the failing test**

Create `ocr_match/tests/test_pipeline_passthrough.py`:

```python
import unittest
from unittest import mock

from ocr_match import pipeline
from ocr_match.models import GajiCredit, ParsedSlip


class _FakeMatchSettings:
    match_amount_tolerance_rp = 1.0


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestPipelinePassthrough(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p = mock.patch("ocr_match.matcher.get_settings",
                       return_value=_FakeMatchSettings())
        self.addCleanup(p.stop)
        p.start()

    async def test_response_carries_full_extractions(self):
        slip_raw = {"documents": [{"source_file": "slip_feb.pdf",
                                   "total_paid": 9_500_000.0, "period": "2025-02"}]}
        mut_raw = {
            "files": [{"filename": "m.pdf", "account": {"nama": "BUDI"}}],
            "credits": [
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "GAJI",
                 "amount": 9_500_000.0, "page": 1, "category": "Gaji"},
                {"source_file": "m.pdf", "tanggal": "2025-03-25", "keterangan": "THR",
                 "amount": 5_000_000.0, "page": 1, "category": "THR"},
            ],
            "audit": {},
        }
        slips = [ParsedSlip(**d) for d in slip_raw["documents"]]
        gaji = [GajiCredit(**c) for c in mut_raw["credits"] if c["category"] == "Gaji"]

        with mock.patch.object(pipeline, "parse_slips", _async((slips, slip_raw))), \
             mock.patch.object(pipeline, "extract_mutations", _async((gaji, mut_raw))):
            resp = await pipeline.run([("slip_feb.pdf", b"a")], [("m.pdf", b"b")])

        # passthrough present and complete
        self.assertEqual(resp.slip_extraction, slip_raw)
        self.assertEqual([c["category"] for c in resp.mutasi_extraction["credits"]],
                         ["Gaji", "THR"])
        # matching still works (Feb slip -> Mar Gaji credit)
        self.assertEqual(len(resp.matches), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_match/tests/test_pipeline_passthrough.py -v`
Expected: FAIL — `run` unpacks `slips = await slip_task` (single value), so the tuple
return breaks it; and `resp.slip_extraction` is `{}`.

- [ ] **Step 3: Update `run()` to unpack tuples and pass through**

In `ocr_match/pipeline.py`, replace the body of `run` from the task creation through
the `return MatchResponse(...)` (currently lines 108–168) with:

```python
    upstream_errors: list[str] = []
    slips: list[ParsedSlip] = []
    credits: list[GajiCredit] = []
    slip_extraction: dict = {}
    mutasi_extraction: dict = {}

    # Step 1 — fan out upstream calls concurrently.
    slip_task = asyncio.create_task(parse_slips(slip_pdfs, password=slip_password))
    mut_task = asyncio.create_task(extract_mutations(mutation_pdfs, password=mutation_password))

    try:
        slips, slip_extraction = await slip_task
    except (UpstreamUnreachableError, UpstreamHttpError) as exc:
        upstream_errors.append(f"ocr_slip: {exc}")
        mut_task.cancel()
        return _empty_response([], [], upstream_errors,
                               slip_extraction={}, mutasi_extraction={})

    try:
        credits, mutasi_extraction = await mut_task
    except (UpstreamUnreachableError, UpstreamHttpError) as exc:
        upstream_errors.append(f"ocr_mutasi: {exc}")
        return _empty_response(slips, [], upstream_errors,
                               slip_extraction=slip_extraction, mutasi_extraction={})

    # Step 2 — tag each item with its month (YYYY-MM).
    for s in slips:
        s.month = _slip_month(s)
    for c in credits:
        c.month = _credit_month(c)

    # Step 3 — run the deterministic matcher across all slips and credits.
    matches, unmatched_slips, unmatched_credits = match_all(slips, credits)

    slip_months = {s.month for s in slips if s.month}
    next_months = set()
    for m in slip_months:
        try:
            y, mo = m.split("-")
            mo_i = int(mo) + 1
            yr_i = int(y)
            if mo_i > 12:
                mo_i, yr_i = 1, yr_i + 1
            next_months.add(f"{yr_i:04d}-{mo_i:02d}")
        except (ValueError, AttributeError):
            pass
    months_processed = sorted(slip_months | next_months)

    return MatchResponse(
        matches=matches,
        unmatched_slips=unmatched_slips,
        unmatched_credits=unmatched_credits,
        audit=MatchAudit(
            slip_count=len(slips),
            credit_count=len(credits),
            matched_count=len(matches),
            months_processed=months_processed,
            matcher_errors=[],
            upstream_errors=upstream_errors,
        ),
        slip_extraction=slip_extraction,
        mutasi_extraction=mutasi_extraction,
    )
```

- [ ] **Step 4: Update `_empty_response` to accept the passthrough blocks**

Replace `_empty_response` (currently lines 171–188) with:

```python
def _empty_response(
    slips: list[ParsedSlip],
    credits: list[GajiCredit],
    upstream_errors: list[str],
    *,
    slip_extraction: dict,
    mutasi_extraction: dict,
) -> MatchResponse:
    return MatchResponse(
        matches=[],
        unmatched_slips=list(slips),
        unmatched_credits=list(credits),
        audit=MatchAudit(
            slip_count=len(slips),
            credit_count=len(credits),
            matched_count=0,
            months_processed=[],
            matcher_errors=[],
            upstream_errors=upstream_errors,
        ),
        slip_extraction=slip_extraction,
        mutasi_extraction=mutasi_extraction,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_match/tests/test_pipeline_passthrough.py -v`
Expected: PASS.

- [ ] **Step 6: Run the whole `ocr_match` test folder**

Run: `.venv\Scripts\python -m pytest ocr_match/tests -v`
Expected: PASS (all Phase-1 tests green).

- [ ] **Step 7: Commit**

```bash
git add ocr_match/pipeline.py ocr_match/tests/test_pipeline_passthrough.py
git commit -m "feat(ocr_match): pass through full slip+mutasi extraction in MatchResponse"
```

---

# PHASE 2 — Rewire `ocr_orchestrator` to the single front door

### Task 2.1: Config — add `ocr_match_url` / `match_timeout_s`, drop slip/mutasi URLs

**Files:**
- Modify: `ocr_orchestrator/config.py`
- Test: `ocr_orchestrator/tests/test_config.py` (existing — confirm it still passes)

- [ ] **Step 1: Edit `Settings`**

In `ocr_orchestrator/config.py`, replace the upstream URL block (currently lines 19–23):

```python
    # Upstream OCR services (compose overrides these with service-DNS URLs).
    ocr_classifier_url: str = "http://127.0.0.1:5001"
    ocr_sk_url: str = "http://127.0.0.1:5002"
    # ocr_match is the single front door for slip + mutasi extraction AND matching.
    ocr_match_url: str = "http://127.0.0.1:5005"
```

Update the module docstring (lines 1–8) — replace the parenthetical about
`ocr_match.config` requiring Azure keys, because the orchestrator no longer imports
`ocr_match`:

```python
"""Runtime configuration loaded once from .env at startup.

The orchestrator never calls Azure directly and no longer imports ``ocr_match``;
it fans out to ``ocr_classifier``, ``ocr_sk``, ``ocr_match`` (the slip+mutasi+match
front door) and ``house_fair_market_value`` over HTTP only. It therefore does NOT
declare any ``AZURE_OPENAI_*`` settings.
"""
```

Add `match_timeout_s` next to the other timeouts (after the `upstream_timeout_s`
line, ~line 31):

```python
    # The ocr_match call runs full OCR+LLM on slips + mutasi, so it is the slowest
    # upstream by far; give it its own generous timeout.
    match_timeout_s: float = 300.0
```

- [ ] **Step 2: Confirm config tests still pass**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_config.py -v`
Expected: PASS. If a test asserts `ocr_slip_url`/`ocr_mutasi_url` defaults, update it
to assert `ocr_match_url == "http://127.0.0.1:5005"` and remove the stale assertions.

- [ ] **Step 3: Commit**

```bash
git add ocr_orchestrator/config.py ocr_orchestrator/tests/test_config.py
git commit -m "feat(orchestrator): config for single ocr_match front door; drop slip/mutasi URLs"
```

---

### Task 2.2: Local date helpers — `slip_dates.py`

Reimplement the two pure helpers locally so nothing imports `ocr_match`. The slip
helper now takes a **dict** (the orchestrator never builds `ParsedSlip`).

**Files:**
- Create: `ocr_orchestrator/slip_dates.py`
- Test: `ocr_orchestrator/tests/test_slip_dates.py` (create)

- [ ] **Step 1: Write the failing test**

Create `ocr_orchestrator/tests/test_slip_dates.py`:

```python
import unittest

from ocr_orchestrator.slip_dates import credit_month, slip_month


class TestSlipMonth(unittest.TestCase):
    def test_period_wins(self):
        self.assertEqual(slip_month({"period": "2025-02",
                                     "source_file": "Apr_2025.pdf"}), "2025-02")

    def test_filename_month_name(self):
        self.assertEqual(slip_month({"source_file": "Slip_Februari_2025.pdf"}),
                         "2025-02")

    def test_filename_iso(self):
        self.assertEqual(slip_month({"source_file": "payslip_2025-04.pdf"}), "2025-04")

    def test_none_when_unparseable(self):
        self.assertIsNone(slip_month({"source_file": "payslip.pdf"}))


class TestCreditMonth(unittest.TestCase):
    def test_slice(self):
        self.assertEqual(credit_month("2025-03-25"), "2025-03")

    def test_short_string(self):
        self.assertIsNone(credit_month("2025"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_slip_dates.py -v`
Expected: FAIL — `ModuleNotFoundError: ocr_orchestrator.slip_dates`.

- [ ] **Step 3: Create `slip_dates.py`**

```python
"""Pure YYYY-MM derivation for slips and credits — local copy of the helpers that
used to live in ``ocr_match.pipeline``. Kept here so the orchestrator imports
nothing from ``ocr_match``. This is slip *placement* logic, not matching.
"""
from __future__ import annotations

import re
from typing import Any, Optional

_MONTHS = {
    "JAN": 1, "JANUARI": 1,
    "FEB": 2, "FEBRUARI": 2,
    "MAR": 3, "MARET": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MAY": 5, "MEI": 5,
    "JUN": 6, "JUNI": 6, "JUNE": 6,
    "JUL": 7, "JULI": 7, "JULY": 7,
    "AUG": 8, "AGT": 8, "AGUSTUS": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OKT": 10, "OKTOBER": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11,
    "DEC": 12, "DES": 12, "DESEMBER": 12, "DECEMBER": 12,
}

_MONTH_NAME_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b[\s_/-]*(\d{4})",
    re.IGNORECASE,
)


def slip_month(slip: dict[str, Any]) -> Optional[str]:
    """Best-effort YYYY-MM for a slip dict: ``period`` first, then filename."""
    period = slip.get("period")
    if isinstance(period, str) and period:
        return period
    name = slip.get("source_file") or ""
    m = _MONTH_NAME_RE.search(name)
    if m:
        mon = _MONTHS[m.group(1).upper()]
        year = int(m.group(2))
        return f"{year:04d}-{mon:02d}"
    m2 = re.search(r"\b(\d{4})[-_/](\d{2})\b", name)
    if m2:
        return f"{int(m2.group(1)):04d}-{int(m2.group(2)):02d}"
    return None


def credit_month(tanggal: Any) -> Optional[str]:
    """Credits use ISO ``YYYY-MM-DD``; slice off the day."""
    if isinstance(tanggal, str) and len(tanggal) >= 7:
        return tanggal[:7]
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_slip_dates.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/slip_dates.py ocr_orchestrator/tests/test_slip_dates.py
git commit -m "feat(orchestrator): local slip/credit month helpers (no ocr_match import)"
```

---

### Task 2.3: Local `MatchView` types in `models.py`

**Files:**
- Modify: `ocr_orchestrator/models.py`

- [ ] **Step 1: Add the view models**

In `ocr_orchestrator/models.py`, after the `VerificationInfo` class (line 82), add:

```python
class MatchedSlipView(BaseModel):
    """The only slip field downstream code reads off a match pair."""
    source_file: Optional[str] = None


class MatchedCreditView(BaseModel):
    """The only credit fields downstream code reads off a match pair."""
    month: Optional[str] = None
    tanggal: Optional[str] = None
    amount: Optional[float] = None


class MatchView(BaseModel):
    """Local, ocr_match-free view of one matched slip<->credit pair.

    Replaces ``ocr_match.models.MatchPair`` for the orchestrator's purposes:
    ``monthly.build_monthly_breakdown`` reads ``.slip.source_file`` and
    ``.credit.month``; ``pipeline._match_pair_view`` also reads ``.credit.tanggal``,
    ``.credit.amount`` and ``.match_pattern``.
    """
    slip: MatchedSlipView = Field(default_factory=MatchedSlipView)
    credit: MatchedCreditView = Field(default_factory=MatchedCreditView)
    match_pattern: Optional[str] = None
```

- [ ] **Step 2: Sanity-check import**

Run: `.venv\Scripts\python -c "from ocr_orchestrator.models import MatchView; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add ocr_orchestrator/models.py
git commit -m "feat(orchestrator): local MatchView types (replace ocr_match.MatchPair)"
```

---

### Task 2.4: Match adapter — rename `verify.py` → `matching.py`

Parses an `ocr_match` `MatchResponse` JSON into the tuple the pipeline consumes.

**Files:**
- Create: `ocr_orchestrator/matching.py`
- Delete: `ocr_orchestrator/verify.py`
- Create: `ocr_orchestrator/tests/test_matching.py`
- Delete: `ocr_orchestrator/tests/test_verify.py`

- [ ] **Step 1: Write the failing test**

Create `ocr_orchestrator/tests/test_matching.py`:

```python
import unittest

from ocr_orchestrator import matching


class TestParseMatchResponse(unittest.TestCase):
    def test_full_response(self):
        payload = {
            "matches": [
                {"slip": {"source_file": "slip_feb.pdf#page-1"},
                 "credit": {"month": "2025-03", "tanggal": "2025-03-25",
                            "amount": 9_500_000.0},
                 "match_pattern": "next_month"},
            ],
            "slip_extraction": {"documents": [
                {"source_file": "slip_feb.pdf#page-1", "worker_name": "BUDI",
                 "total_paid": 9_500_000.0, "period": "2025-02"},
            ]},
            "mutasi_extraction": {
                "files": [{"filename": "m.pdf", "account": {"nama": "BUDI SANTOSO"}}],
                "credits": [
                    {"source_file": "m.pdf", "tanggal": "2025-03-25", "amount": 9_500_000.0,
                     "category": "Gaji"},
                    {"source_file": "m.pdf", "tanggal": "2025-03-25", "amount": 5_000_000.0,
                     "category": "THR"},
                ],
                "audit": {},
            },
        }
        slip_docs, credits, mut_files, matches, verified = \
            matching.parse_match_response(payload)

        self.assertEqual(len(slip_docs), 1)
        self.assertEqual(slip_docs[0]["worker_name"], "BUDI")
        self.assertEqual([c["category"] for c in credits], ["Gaji", "THR"])
        self.assertEqual(mut_files[0]["account"]["nama"], "BUDI SANTOSO")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].slip.source_file, "slip_feb.pdf#page-1")
        self.assertEqual(matches[0].credit.month, "2025-03")
        self.assertEqual(matches[0].match_pattern, "next_month")
        self.assertEqual(verified, {"2025-03"})

    def test_month_falls_back_to_tanggal(self):
        payload = {
            "matches": [
                {"slip": {"source_file": "s.pdf"},
                 "credit": {"tanggal": "2025-07-25", "amount": 1.0},
                 "match_pattern": "same_month"},
            ],
            "slip_extraction": {"documents": []},
            "mutasi_extraction": {"files": [], "credits": [], "audit": {}},
        }
        _slips, _credits, _files, matches, verified = \
            matching.parse_match_response(payload)
        self.assertEqual(matches[0].credit.month, "2025-07")
        self.assertEqual(verified, {"2025-07"})

    def test_empty_payload(self):
        slip_docs, credits, mut_files, matches, verified = \
            matching.parse_match_response({})
        self.assertEqual(slip_docs, [])
        self.assertEqual(credits, [])
        self.assertEqual(mut_files, [])
        self.assertEqual(matches, [])
        self.assertEqual(verified, set())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: ocr_orchestrator.matching`.

- [ ] **Step 3: Create `matching.py`**

```python
"""Adapt an ocr_match /api/v1/match response into what the pipeline consumes.

ocr_match is the single front door: its response carries full slip extraction,
full mutasi extraction (all categories + account/files), and the slip<->Gaji match
result. This module reads that JSON and returns plain dicts + local MatchView
objects — it imports nothing from ocr_match.
"""
from __future__ import annotations

from typing import Any

from .models import MatchedCreditView, MatchedSlipView, MatchView
from .slip_dates import credit_month


def parse_match_response(
    payload: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict], list[MatchView], set[str]]:
    """Return ``(slip_docs, credits, mut_files, matches, verified_months)``.

    - ``slip_docs``: every parsed slip dict (``slip_extraction.documents``).
    - ``credits``: every mutasi credit dict, ALL categories
      (``mutasi_extraction.credits``).
    - ``mut_files``: mutasi per-file dicts incl. ``account`` (``mutasi_extraction.files``).
    - ``matches``: local ``MatchView`` list.
    - ``verified_months``: YYYY-MM buckets that produced a match.
    """
    slip_extraction = payload.get("slip_extraction") or {}
    mutasi_extraction = payload.get("mutasi_extraction") or {}

    slip_docs = list(slip_extraction.get("documents") or [])
    credits = list(mutasi_extraction.get("credits") or [])
    mut_files = list(mutasi_extraction.get("files") or [])

    matches: list[MatchView] = []
    verified_months: set[str] = set()
    for m in payload.get("matches") or []:
        slip = m.get("slip") or {}
        credit = m.get("credit") or {}
        month = credit.get("month") or credit_month(credit.get("tanggal"))
        matches.append(MatchView(
            slip=MatchedSlipView(source_file=slip.get("source_file")),
            credit=MatchedCreditView(
                month=month,
                tanggal=credit.get("tanggal"),
                amount=credit.get("amount"),
            ),
            match_pattern=m.get("match_pattern"),
        ))
        if month:
            verified_months.add(month)

    return slip_docs, credits, mut_files, matches, verified_months
```

- [ ] **Step 4: Delete the old verify module + test**

```bash
git rm ocr_orchestrator/verify.py ocr_orchestrator/tests/test_verify.py
```

- [ ] **Step 5: Run to verify the new test passes**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_matching.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add ocr_orchestrator/matching.py ocr_orchestrator/tests/test_matching.py
git commit -m "feat(orchestrator): match-response adapter (replaces in-process verify)"
```

---

### Task 2.5: `monthly.py` — drop `ocr_match`, use local helper + `MatchView`

**Files:**
- Modify: `ocr_orchestrator/monthly.py`
- Test: `ocr_orchestrator/tests/test_monthly.py` (existing — must stay green)

- [ ] **Step 1: Replace the imports + slip-month call**

In `ocr_orchestrator/monthly.py`, replace the two `ocr_match` imports (lines 18–19):

```python
from .slip_dates import slip_month as _slip_month
```

Remove the now-unused `ParsedSlip` usage. Replace the slip-home line (currently
line 100, `home = _slip_month(ParsedSlip(**d))`) with:

```python
            home = _slip_month(d)
```

Also drop the docstring sentence that references `ocr_match.pipeline` (lines 9–11
area) — replace it with:

```python
Reuses ``slip_dates.slip_month`` (the non-trivial month derivation: slip ``period``
then filename parsing). Credit months are the same ``tanggal[:7]`` slice
``income.py`` uses.
```

- [ ] **Step 2: Run the existing monthly tests**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_monthly.py -v`
Expected: PASS — `test_monthly.py` already uses a `SimpleNamespace` stand-in with
`.slip.source_file` / `.credit.month`, which `MatchView` matches; no test change
needed.

- [ ] **Step 3: Commit**

```bash
git add ocr_orchestrator/monthly.py
git commit -m "refactor(orchestrator): monthly breakdown uses local slip_dates, no ocr_match"
```

---

### Task 2.6: `upstream.py` — add `match_documents`, delete slip/mutasi clients

**Files:**
- Modify: `ocr_orchestrator/upstream.py`
- Test: `ocr_orchestrator/tests/test_upstream.py` (existing — extend)

- [ ] **Step 1: Add failing tests for `match_documents`**

Append to `ocr_orchestrator/tests/test_upstream.py`, before the `if __name__` guard.
Note the existing `_FakeClient.post` signature only accepts `json=`; add a variant
that accepts `files=`/`data=`:

```python
class _FakeMultipartClient:
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, files=None, data=None):
        if self._exc:
            raise self._exc
        return self._resp


def _patch_multipart(resp=None, exc=None):
    return mock.patch.object(upstream.httpx, "AsyncClient",
                             lambda *a, **k: _FakeMultipartClient(resp=resp, exc=exc))


class TestMatchDocuments(unittest.IsolatedAsyncioTestCase):
    async def test_success_returns_json(self):
        body = {"matches": [], "slip_extraction": {"documents": []},
                "mutasi_extraction": {"files": [], "credits": [], "audit": {}}}
        with _patch_multipart(resp=_FakeResp(200, body)):
            out = await upstream.match_documents([("s.pdf", b"a")], [("m.pdf", b"b")])
        self.assertIn("mutasi_extraction", out)

    async def test_transport_error_raises_unreachable(self):
        with _patch_multipart(exc=httpx.ConnectError("refused")):
            with self.assertRaises(upstream.UpstreamUnreachableError):
                await upstream.match_documents([("s.pdf", b"a")], [("m.pdf", b"b")])

    async def test_4xx_raises_http_error(self):
        with _patch_multipart(resp=_FakeResp(400, text="need both groups")):
            with self.assertRaises(upstream.UpstreamHttpError):
                await upstream.match_documents([("s.pdf", b"a")], [("m.pdf", b"b")])
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_upstream.py::TestMatchDocuments -v`
Expected: FAIL — `AttributeError: module 'ocr_orchestrator.upstream' has no attribute 'match_documents'`.

- [ ] **Step 3: Add `match_documents`; delete `parse_slips` + `extract_mutations`**

In `ocr_orchestrator/upstream.py`, **delete** the `parse_slips` (lines 62–77) and
`extract_mutations` (lines 80–93) functions entirely. Update the module docstring
(lines 1–6) to:

```python
"""Async httpx clients for the orchestrator's upstreams.

The orchestrator parses no PDFs itself: ``ocr_match`` is the single front door for
slip + mutasi extraction AND matching, ``ocr_classifier`` labels docs, ``ocr_sk``
parses employment letters, and ``house_fair_market_value`` prices collateral. Each
function takes already-read ``(filename, bytes)`` tuples (or a JSON body) and
returns the loosely-typed JSON the pipeline consumes.
"""
```

Add this function (e.g. after `classify_documents`):

```python
async def match_documents(
    slip_pdfs: list[tuple[str, bytes]],
    mutasi_pdfs: list[tuple[str, bytes]],
    *,
    password: str | None = None,
) -> dict[str, Any]:
    """POST slip + mutasi PDFs to ocr_match:/api/v1/match. Returns the full
    MatchResponse JSON: ``matches``, ``slip_extraction`` (full ocr_slip body),
    ``mutasi_extraction`` (full ocr_mutasi body, all categories), ``audit``.

    The single orchestrator ``password`` is forwarded as both ``slip_password`` and
    ``mutation_password`` (ocr_match takes them separately)."""
    s = get_settings()
    url = f"{s.ocr_match_url}/api/v1/match"
    files = (
        [("slips", (name, data, "application/pdf")) for name, data in slip_pdfs]
        + [("mutations", (name, data, "application/pdf")) for name, data in mutasi_pdfs]
    )
    data: dict[str, str] = {}
    if password:
        data["slip_password"] = password
        data["mutation_password"] = password
    try:
        async with httpx.AsyncClient(timeout=s.match_timeout_s) as client:
            r = await client.post(url, files=files, data=data)
    except httpx.TransportError as exc:
        raise UpstreamUnreachableError(
            f"ocr_match not reachable at {url}: {exc}"
        ) from exc
    if r.status_code >= 400:
        raise UpstreamHttpError("ocr_match", r.status_code, r.text)
    return r.json()
```

- [ ] **Step 4: Run the upstream tests**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_upstream.py -v`
Expected: PASS (FMV tests + 3 new `match_documents` tests).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/upstream.py ocr_orchestrator/tests/test_upstream.py
git commit -m "feat(orchestrator): match_documents client; remove slip/mutasi clients"
```

---

### Task 2.7: Rename the tracked stage `verify` → `acquire`

**Files:**
- Modify: `ocr_orchestrator/jobs.py`
- Test: `ocr_orchestrator/tests/test_jobs.py` (existing)

- [ ] **Step 1: Update `_DEFAULT_STAGES`**

In `ocr_orchestrator/jobs.py`, replace line 17:

```python
_DEFAULT_STAGES = ("classify", "extract", "acquire", "aggregate", "fmv", "decide")
```

- [ ] **Step 2: Update the stage-list test**

In `ocr_orchestrator/tests/test_jobs.py` line 12, replace the expected list:

```python
                         ["classify", "extract", "acquire", "aggregate", "fmv", "decide"])
```

- [ ] **Step 3: Run the jobs test**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_jobs.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add ocr_orchestrator/jobs.py ocr_orchestrator/tests/test_jobs.py
git commit -m "refactor(orchestrator): rename verify stage to acquire"
```

---

### Task 2.8: Rewire `pipeline.py` — extract=`ocr_sk` only, new `acquire` stage, D1 degrade

This is the integration task. It removes the slip/mutasi extract calls, replaces the
verify stage with the `ocr_match`-backed `acquire` stage, moves slip/mutasi
`doc_results` attachment after acquire, and degrades to no-income on outage.

**Files:**
- Modify: `ocr_orchestrator/pipeline.py`
- Test: `ocr_orchestrator/tests/test_pipeline.py` (rewrite mocks)

- [ ] **Step 1: Rewrite the pipeline tests to mock `match_documents`**

Replace the whole body of `ocr_orchestrator/tests/test_pipeline.py` with:

```python
import unittest
from unittest import mock

from ocr_orchestrator import pipeline
from ocr_orchestrator.jobs import JobStore


def _async(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn


def _async_raise(exc):
    async def _fn(*args, **kwargs):
        raise exc
    return _fn


def _match_payload(*, worker="BUDI", account="BUDI SANTOSO", amount=9_500_000.0,
                   tanggal="2025-03-25", period="2025-02", matched=True,
                   extra_credits=()):
    credits = [{"source_file": "mut.pdf", "tanggal": tanggal, "keterangan": "GAJI",
                "amount": amount, "page": 1, "category": "Gaji"}]
    credits.extend(extra_credits)
    payload = {
        "matches": [],
        "slip_extraction": {"documents": [
            {"source_file": "slip_feb.pdf#page-1", "worker_name": worker,
             "total_paid": amount, "period": period},
        ]},
        "mutasi_extraction": {
            "files": [{"filename": "mut.pdf", "account": {"nama": account}}],
            "credits": credits, "audit": {},
        },
    }
    if matched:
        payload["matches"] = [{
            "slip": {"source_file": "slip_feb.pdf#page-1"},
            "credit": {"month": tanggal[:7], "tanggal": tanggal, "amount": amount},
            "match_pattern": "next_month",
        }]
    return payload


def _classify():
    return _async([
        {"filename": "slip_feb.pdf", "document_type": "slip", "confidence": "high"},
        {"filename": "mut.pdf", "document_type": "mutasi", "confidence": "high"},
    ])


_FILES = [("slip_feb.pdf", b"a"), ("mut.pdf", b"b")]


class TestRunJob(unittest.IsolatedAsyncioTestCase):
    async def test_happy_path_bank_verified(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload())):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.income.basis, "bank_verified")
        self.assertEqual(job.result.income.monthly_qualifying_income, 9_500_000)
        self.assertEqual(job.result.applicant.name, "BUDI")
        self.assertEqual(job.result.applicant.name_source, "slip")
        self.assertEqual(job.result.verification.verified_month_count, 1)

        slip_doc = next(d for d in job.result.documents if d.document_type == "slip")
        self.assertEqual(slip_doc.extracted["worker_name"], "BUDI")
        mut_doc = next(d for d in job.result.documents if d.document_type == "mutasi")
        self.assertEqual(mut_doc.extracted["account"]["nama"], "BUDI SANTOSO")

        row = job.result.income.monthly_breakdown[0]
        self.assertEqual(row.month, "2025-03")
        self.assertEqual(row.source, "bank_verified")
        self.assertEqual(row.total_paid, 9_500_000)

    async def test_classifier_down_fails_job(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents",
                               _async_raise(UpstreamUnreachableError("classifier down"))):
            await pipeline.run_job(store, job.id, [("x.pdf", b"a")],
                                   bonus_accept_pct=0.0, password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("classifier", job.error)

    async def test_ocr_match_down_degrades_to_no_income(self):
        from ocr_orchestrator.upstream import UpstreamUnreachableError
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async_raise(UpstreamUnreachableError("ocr_match down"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "completed")        # D1: degrade, not fail
        self.assertEqual(job.result.income.basis, "none")
        self.assertTrue(job.result.audit.extractor_errors)
        acquire = next(s for s in job.stages if s.name == "acquire")
        self.assertEqual(acquire.status, "completed")

    async def test_unexpected_internal_error_fails_job(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload())), \
             mock.patch.object(pipeline, "compute_income",
                               side_effect=RuntimeError("boom")):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertEqual(job.status, "failed")
        self.assertIn("internal error", job.error)

    def _collateral_loan(self):
        from ocr_orchestrator.models import CollateralInput, LoanRequest
        return (CollateralInput(luas_tanah=80.0, luas_bangunan=50.0),
                LoanRequest(loan_amount=700_000_000, tenor_months=240,
                            annual_interest_rate=0.10))

    async def test_fmv_and_decide_run_when_inputs_present(self):
        collateral, loan = self._collateral_loan()
        fmv = _async({"land_value": 600_000_000, "building_value": 400_000_000,
                      "fair_value": 1_000_000_000, "location_matched": True,
                      "backend": "linear", "warnings": []})
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))), \
             mock.patch.object(pipeline.upstream, "predict_fair_value", fmv):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, collateral=collateral, loan=loan)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.result.fmv.fair_value, 1_000_000_000)
        self.assertEqual(job.result.decision.recommendation, "eligible")
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "completed")

    async def test_stages_skipped_when_no_collateral_or_loan(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None)
        self.assertIsNone(job.result.fmv)
        self.assertIsNone(job.result.decision)
        self.assertEqual(next(s for s in job.stages if s.name == "fmv").status, "skipped")
        self.assertEqual(next(s for s in job.stages if s.name == "decide").status, "skipped")

    async def test_input_warnings_land_in_audit(self):
        store = JobStore(retention=10)
        job = await store.create()
        with mock.patch.object(pipeline.upstream, "classify_documents", _classify()), \
             mock.patch.object(pipeline.upstream, "parse_sk", _async({"summary": {}})), \
             mock.patch.object(pipeline.upstream, "match_documents",
                               _async(_match_payload(amount=20_000_000.0,
                                                     period="2025-03"))):
            await pipeline.run_job(store, job.id, _FILES, bonus_accept_pct=0.0,
                                   password=None, input_warnings=["partial loan ignored"])
        self.assertIn("partial loan ignored", job.result.audit.warnings)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify the rewritten tests fail**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_pipeline.py -v`
Expected: FAIL — pipeline still imports `verify` and calls `parse_slips`/
`extract_mutations`; `match_documents` isn't wired; `acquire` stage doesn't exist.

- [ ] **Step 3: Update pipeline imports**

In `ocr_orchestrator/pipeline.py`, replace the verify import (line 33):

```python
from .matching import parse_match_response
```

- [ ] **Step 4: Replace the extract + verify stages with extract(sk) + acquire**

Replace the block from `# ---- Stage 2: extract` through the end of the verify stage
(currently lines 123–199) with:

```python
    # ---- Stage 2: extract (ocr_sk only; slip+mutasi now come from ocr_match) ----
    await store.set_stage(job_id, "extract", "running")
    t0 = time.perf_counter()
    sk_response: dict[str, Any] = {}
    if buckets.sk:
        try:
            sk_response = await upstream.parse_sk(buckets.sk, password=password)
        except _UpstreamError as exc:
            audit.extractor_errors.append(f"ocr_sk: {exc}")
    timings["extract"] = (time.perf_counter() - t0) * 1000
    await store.set_stage(job_id, "extract", "completed")

    # ---- Stage 3: acquire (single ocr_match call: slips + mutasi + match) ----
    await store.set_stage(job_id, "acquire", "running")
    t0 = time.perf_counter()
    slip_docs: list[dict[str, Any]] = []
    credits: list[dict[str, Any]] = []
    mut_files: list[dict[str, Any]] = []
    matches: list[Any] = []
    verified_months: set[str] = set()

    if not buckets.slips or not buckets.mutasi:
        # ocr_match requires BOTH a slip and a mutasi PDF; a one-sided bundle can
        # produce no verified income under the single-front-door design.
        audit.warnings.append(
            "ocr_match needs both a slip and a bank statement; income skipped."
        )
        await store.set_stage(job_id, "acquire", "completed")
    else:
        try:
            payload = await upstream.match_documents(
                buckets.slips, buckets.mutasi, password=password
            )
            slip_docs, credits, mut_files, matches, verified_months = \
                parse_match_response(payload)
            await store.set_stage(job_id, "acquire", "completed")
        except _UpstreamError as exc:  # D1: degrade to no-income, don't fail
            logger.warning("acquire stage degraded: %s", exc)
            audit.extractor_errors.append(f"ocr_match: {exc}")
            audit.warnings.append("ocr_match unreachable; income could not be verified.")
            await store.set_stage(job_id, "acquire", "completed", str(exc))
    timings["acquire"] = (time.perf_counter() - t0) * 1000

    # Attach per-document extraction payloads (by filename).
    slip_by_file: dict[str, dict[str, Any]] = {}
    for _d in slip_docs:
        slip_by_file.setdefault(_slip_base(_d.get("source_file")), _d)
    mut_by_file = {f.get("filename"): f for f in mut_files}
    for d in doc_results:
        if d.document_type == "slip":
            d.extracted = slip_by_file.get(d.filename)
        elif d.document_type == "mutasi":
            d.extracted = mut_by_file.get(d.filename)
        elif d.document_type == "sk":
            d.extracted = sk_response or None

    verification = VerificationInfo(
        matched_count=len(matches),
        verified_month_count=len(verified_months),
        matched_pairs=[_match_pair_view(p) for p in matches],
    )
```

- [ ] **Step 5: Update the aggregate stage's slip_total_paids source**

The aggregate stage (currently lines 201–215) already reads `slip_docs` and
`credits`, which are now produced by stage 3. No change to its body is required —
but confirm the `credits` it uses is the local variable from the acquire stage (it
is, after Step 4 removed the old `credits = mutasi_payload.get(...)` line). Leave
`compute_income(...)` / `build_monthly_breakdown(...)` as-is.

- [ ] **Step 6: Fix the assemble stage's mutasi account source**

In the assemble stage (currently line 256), replace:

```python
    mutasi_accounts = [f.get("account", {}) for f in mut_files]
```

(`mut_files` is now the local variable from stage 3 — confirm the old `mut_files`
binding from the deleted extract stage is gone.)

- [ ] **Step 7: Run the pipeline tests**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_pipeline.py -v`
Expected: PASS (all rewritten tests green).

- [ ] **Step 8: Commit**

```bash
git add ocr_orchestrator/pipeline.py ocr_orchestrator/tests/test_pipeline.py
git commit -m "feat(orchestrator): single ocr_match acquire stage; drop own slip/mutasi extract (D1 degrade)"
```

---

### Task 2.9: Decoupling guard + full suite + docs

**Files:**
- Create: `ocr_orchestrator/tests/test_no_ocr_match_import.py`
- Modify: `ocr_orchestrator/README.md`

- [ ] **Step 1: Write the decoupling-guard test**

Create `ocr_orchestrator/tests/test_no_ocr_match_import.py`:

```python
"""Guard: the orchestrator must not import ocr_match (single front door is HTTP)."""
import pathlib
import unittest

_PKG = pathlib.Path(__file__).resolve().parent.parent


class TestNoOcrMatchImport(unittest.TestCase):
    def test_no_ocr_match_imports(self):
        offenders = []
        for path in _PKG.rglob("*.py"):
            if "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if "import ocr_match" in text or "from ocr_match" in text:
                offenders.append(str(path.relative_to(_PKG)))
        self.assertEqual(offenders, [], f"ocr_match imported in: {offenders}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the guard test**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests/test_no_ocr_match_import.py -v`
Expected: PASS. If it fails, the named file still imports `ocr_match` — fix it.

- [ ] **Step 3: Run the FULL orchestrator + ocr_match suites**

Run: `.venv\Scripts\python -m pytest ocr_orchestrator/tests ocr_match/tests -v`
Expected: PASS — no failures, no errors.

- [ ] **Step 4: Update the orchestrator README**

In `ocr_orchestrator/README.md`, update the intro paragraph (lines 3–7) to reflect
the single front door. Replace it with:

```markdown
Sixth sibling service (port **8500**). Accepts an unlabeled PDF bundle,
classifies each document via `ocr_classifier`, parses employment letters via
`ocr_sk`, and calls **`ocr_match`** as the single front door for salary-slip and
bank-statement extraction **and** slip↔Gaji matching — sourcing full slip data,
all-category bank credits, and the match result from one response. It aggregates
one **monthly qualifying-income** figure, optionally prices collateral
(`house_fair_market_value`) and runs an approve/refer decision. Async job + polling.
```

Update the "Needs the four upstream services" line (~line 21) to:

```markdown
Needs `ocr_classifier`, `ocr_sk`, and `ocr_match` running (set `OCR_CLASSIFIER_URL`,
`OCR_SK_URL`, `OCR_MATCH_URL`), plus `house_fair_market_value` if you send
collateral. The orchestrator no longer calls `ocr_slip` / `ocr_mutasi` directly —
`ocr_match` does. If `ocr_match` is unreachable the job still completes with no
verified income (degraded).
```

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/tests/test_no_ocr_match_import.py ocr_orchestrator/README.md
git commit -m "test(orchestrator): guard against ocr_match imports; refresh README"
```

---

## Self-review checklist (run after implementation)

- [ ] **Spec coverage:** §3 contract → Tasks 1.1–1.3; §4 ocr_match changes →
  Phase 1; §5 component table → Tasks 2.1–2.8; §6 stages → Task 2.8 + 2.7; §7
  multiple/unmatched slips → covered by `slip_docs` always being the full set
  (Task 2.4) + existing `test_monthly` slip_only cases; §8 D1 degrade → Task 2.8
  `test_ocr_match_down_degrades_to_no_income`; §9 testing → every task is TDD +
  Task 2.9 guard; §10 out of scope → respected (no income-formula/fmv/decide edits).
- [ ] **Placeholder scan:** none — every step has full code or an exact command.
- [ ] **Type consistency:** `parse_match_response` returns
  `(slip_docs, credits, mut_files, matches, verified_months)` and the pipeline
  unpacks exactly that order (Task 2.8 Step 4). `MatchView.slip.source_file` /
  `.credit.month` / `.match_pattern` match both `monthly.py` and `_match_pair_view`.
  `match_documents(slip_pdfs, mutasi_pdfs, *, password)` matches the pipeline call.
  Stage name `acquire` is identical in `jobs.py`, `pipeline.py`, and the tests.

## Notes for the implementer

- Always run pytest **from the repo root** (`.venv\Scripts\python -m pytest ...`),
  never from inside a service folder, or imports fail (`ModuleNotFoundError`).
- Phase 1 and Phase 2 are independently committable, but **do not** deploy Phase 2
  against an `ocr_match` that hasn't shipped Phase 1 — the `slip_extraction` /
  `mutasi_extraction` fields won't exist and every job degrades to no-income.
- `pipeline.py` still imports `decision.decide`, `identity.resolve_applicant_name`,
  `income.compute_income`, `monthly.build_monthly_breakdown` — leave those intact.
  After Task 2.8, double-check no dangling references to the removed `parse_slips`,
  `extract_mutations`, `gaji_credits`, `mutasi_payload`, or `slip_res` locals remain
  (a stray reference will surface as a `NameError` in the pipeline tests).
```
