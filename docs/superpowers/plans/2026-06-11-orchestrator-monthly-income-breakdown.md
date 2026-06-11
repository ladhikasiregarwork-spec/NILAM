# Per-Month Income Breakdown Implementation Plan

> **Status — 2026-06-11: ✅ Implemented & shipped to `main` (tests passing).** The step checkboxes below are the original execution checklist, kept for history and not individually re-ticked (a few `(Optional)` manual/networked steps were not run).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive `income.monthly_breakdown` table to the `ocr_orchestrator` result — one row per month (union of bank + slip months), bank-first, with a per-row `source` flag.

**Architecture:** A new pure module `ocr_orchestrator/monthly.py` joins the mutasi `credits[]` and slip `documents[]` the pipeline already fetched, keyed by month, reusing the verify stage's `MatchPair[]` to home each slip to the right bank month (X+1 payroll-lag aware). A new `MonthlyIncomeRow` pydantic model hangs the rows off the existing `IncomeBreakdown`. The aggregate qualifying-income math in `income.py` is untouched.

**Tech Stack:** Python 3.12, FastAPI/pydantic v2, `unittest` (repo convention — see `ocr_orchestrator/tests/`). Run everything from the **repo root** with `.venv/Scripts/python` (Windows).

**Spec:** `docs/superpowers/specs/2026-06-11-orchestrator-monthly-income-breakdown-design.md`

**Before you start:** the repo is on `main`. Create a feature branch first:
```bash
git checkout -b feat/orchestrator-monthly-income
```
(Plan & spec live under `docs/`, which is gitignored locally — that is intentional; do **not** try to commit them. All task commits below touch only `ocr_orchestrator/*.py`, which is tracked normally.)

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `ocr_orchestrator/models.py` | Add `MonthlyIncomeRow` + `RowSource`; add `monthly_breakdown` field to `IncomeBreakdown` | Modify |
| `ocr_orchestrator/monthly.py` | Pure `build_monthly_breakdown(credits, slip_docs, matches)` join | Create |
| `ocr_orchestrator/pipeline.py` | Call `build_monthly_breakdown` in the aggregate stage | Modify |
| `ocr_orchestrator/tests/test_models.py` | Unit test for the new model + default | Modify |
| `ocr_orchestrator/tests/test_monthly.py` | Unit tests for the join (all `source` flags, edges) | Create |
| `ocr_orchestrator/tests/test_pipeline.py` | Assert breakdown is present end-to-end | Modify |

---

## Task 1: Add the `MonthlyIncomeRow` model

**Files:**
- Modify: `ocr_orchestrator/models.py`
- Test: `ocr_orchestrator/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `ocr_orchestrator/tests/test_models.py` (inside the file, as new test methods on the existing test class or a new class — use a new class to be safe):

```python
class TestMonthlyIncomeRow(unittest.TestCase):
    def test_row_validates_and_allows_nulls(self):
        from ocr_orchestrator.models import MonthlyIncomeRow

        row = MonthlyIncomeRow(
            month="2026-04",
            fixed_routine_income=8_000_000.0,
            thr=8_000_000.0,
            bonus_non_fixed=0.0,
            deduction=None,
            total_paid=None,
            bank_salary_credit=8_000_000.0,
            source="bank_only",
        )
        self.assertEqual(row.month, "2026-04")
        self.assertIsNone(row.deduction)
        self.assertEqual(row.source, "bank_only")

    def test_income_breakdown_has_empty_breakdown_by_default(self):
        from ocr_orchestrator.models import IncomeBreakdown

        ib = IncomeBreakdown(
            n_statement_months=0,
            avg_monthly_gaji_insentif=0.0,
            monthly_thr=0.0,
            bonus_total=0.0,
            bonus_accept_pct=0.0,
            bonus_monthly=0.0,
            monthly_qualifying_income=None,
            basis="none",
            verified_month_count=0,
        )
        self.assertEqual(ib.monthly_breakdown, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_models.py::TestMonthlyIncomeRow -v
```
Expected: FAIL — `ImportError: cannot import name 'MonthlyIncomeRow'` (and the breakdown assertion errors).

- [ ] **Step 3: Add the model and field**

In `ocr_orchestrator/models.py`, add `RowSource` next to the other `Literal` aliases (just below the `IncomeBasis = Literal[...]` line near the top):

```python
RowSource = Literal["bank_verified", "bank_unverified", "bank_only", "slip_only"]
```

Add the `MonthlyIncomeRow` class immediately **above** the `class IncomeBreakdown(BaseModel):` definition:

```python
class MonthlyIncomeRow(BaseModel):
    """One calendar month of income, joined from bank credits + a salary slip.

    Bank-first (spec §3): bank credits are the source of truth for the income
    amounts; the matched slip supplies ``deduction``/``total_paid``.

    NOTE: ``bonus_non_fixed`` intentionally includes bank ``Insentif`` (spec §3,
    decision 4). This differs from the aggregate ``IncomeBreakdown``, which counts
    Insentif AS salary (``avg_monthly(Gaji + Insentif)``). The two views serve
    different purposes and are allowed to diverge — do not "fix" this.

    ``null`` means "no data source for this field"; ``0`` means "a source covered
    it and the amount was zero" (e.g. a normal no-THR month on a bank row shows
    ``thr == 0``, not ``null``).
    """
    month: str                              # "YYYY-MM" — the "month payment" key
    fixed_routine_income: Optional[float]   # bank Gaji   (slip pokok if slip_only)
    thr: Optional[float]                    # bank THR    (null if slip_only)
    bonus_non_fixed: Optional[float]        # bank Bonus + Insentif (slip incentive if slip_only)
    deduction: Optional[float]              # slip only
    total_paid: Optional[float]             # slip only
    bank_salary_credit: Optional[float]     # bank Gaji credit amount (null if slip_only)
    source: RowSource
```

Add the new field to the **end** of `class IncomeBreakdown(BaseModel)` (after the `warnings` field):

```python
    monthly_breakdown: list[MonthlyIncomeRow] = Field(default_factory=list)
```

(`Literal`, `Optional`, `Field`, and `BaseModel` are already imported at the top of `models.py` — no new imports needed.)

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_models.py -v
```
Expected: PASS (all model tests, old and new).

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/models.py ocr_orchestrator/tests/test_models.py
git commit -m "feat(orchestrator): add MonthlyIncomeRow model + income.monthly_breakdown field"
```

---

## Task 2: Implement the `build_monthly_breakdown` join

**Files:**
- Create: `ocr_orchestrator/monthly.py`
- Test: `ocr_orchestrator/tests/test_monthly.py`

The function reads the mutasi `credits[]` dicts directly (like `income.py` does — robust, no model construction), and reuses `_slip_month` from `ocr_match.pipeline` for slip-month derivation (the non-trivial logic: `period` then filename parsing). It only needs two attributes off each `MatchPair`: `pair.slip.source_file` and `pair.credit.month`.

- [ ] **Step 1: Write the failing test**

Create `ocr_orchestrator/tests/test_monthly.py`:

```python
import unittest
from types import SimpleNamespace

from ocr_orchestrator.monthly import build_monthly_breakdown


def _credit(category, amount, tanggal, source_file="mut.pdf"):
    return {
        "source_file": source_file, "tanggal": tanggal,
        "keterangan": category.upper(), "amount": amount,
        "page": 1, "category": category,
    }


def _slip(source_file, total_paid, deduction=0.0, pokok=0.0,
          incentive=0.0, period=None):
    return {
        "source_file": source_file, "total_paid": total_paid,
        "deduction": deduction, "pokok": pokok, "incentive": incentive,
        "period": period,
    }


def _match(slip_source_file, credit_month):
    """Minimal stand-in for ocr_match.models.MatchPair.

    build_monthly_breakdown only reads pair.slip.source_file and
    pair.credit.month; the real MatchPair shape is covered by the
    pipeline end-to-end test.
    """
    return SimpleNamespace(
        slip=SimpleNamespace(source_file=slip_source_file),
        credit=SimpleNamespace(month=credit_month),
    )


def _by_month(rows):
    return {r.month: r for r in rows}


class TestBuildMonthlyBreakdown(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(build_monthly_breakdown([], [], []), [])

    def test_bank_verified_row(self):
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-03")]
        matches = [_match("slip.pdf", "2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.month, "2026-03")
        self.assertEqual(r.source, "bank_verified")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.bank_salary_credit, 8_000_000)
        self.assertEqual(r.thr, 0.0)               # bank row, no THR -> real 0
        self.assertEqual(r.bonus_non_fixed, 0.0)
        self.assertEqual(r.deduction, 750_000)     # from slip
        self.assertEqual(r.total_paid, 7_250_000)

    def test_bank_unverified_row_unmatched_slip_same_month(self):
        # Gaji credit + a slip for the same period that did NOT match.
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches=[])
        r = _by_month(rows)["2026-03"]
        self.assertEqual(r.source, "bank_unverified")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.deduction, 750_000)     # slip still attached
        self.assertEqual(r.total_paid, 7_250_000)

    def test_bank_only_row_nulls_slip_fields(self):
        credits = [_credit("Gaji", 8_000_000, "2026-04-25"),
                   _credit("THR", 8_000_000, "2026-04-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-04"]
        self.assertEqual(r.source, "bank_only")
        self.assertEqual(r.fixed_routine_income, 8_000_000)
        self.assertEqual(r.thr, 8_000_000)
        self.assertIsNone(r.deduction)             # no slip -> null
        self.assertIsNone(r.total_paid)

    def test_thr_only_month_fixed_is_zero_not_null(self):
        credits = [_credit("THR", 8_000_000, "2026-04-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-04"]
        self.assertEqual(r.source, "bank_only")
        self.assertEqual(r.fixed_routine_income, 0.0)   # statement covered it -> 0
        self.assertEqual(r.bank_salary_credit, 0.0)
        self.assertEqual(r.thr, 8_000_000)

    def test_slip_only_row(self):
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       pokok=6_500_000, incentive=1_500_000, period="2026-05")]
        rows = build_monthly_breakdown(credits=[], slip_docs=slips, matches=[])
        r = _by_month(rows)["2026-05"]
        self.assertEqual(r.source, "slip_only")
        self.assertEqual(r.fixed_routine_income, 6_500_000)   # slip pokok
        self.assertEqual(r.bonus_non_fixed, 1_500_000)        # slip incentive
        self.assertIsNone(r.thr)                              # slip can't split
        self.assertIsNone(r.bank_salary_credit)              # no bank data
        self.assertEqual(r.deduction, 750_000)
        self.assertEqual(r.total_paid, 7_250_000)

    def test_insentif_goes_to_non_fixed(self):
        credits = [_credit("Gaji", 8_000_000, "2026-03-25"),
                   _credit("Insentif", 500_000, "2026-03-25"),
                   _credit("Bonus", 1_000_000, "2026-03-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        r = _by_month(rows)["2026-03"]
        self.assertEqual(r.fixed_routine_income, 8_000_000)        # Gaji only
        self.assertEqual(r.bonus_non_fixed, 1_500_000)            # Bonus + Insentif

    def test_lainnya_does_not_create_a_row(self):
        credits = [_credit("Lainnya", 50_000, "2026-03-02")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        self.assertEqual(rows, [])

    def test_x_plus_1_homing_puts_slip_in_credit_month(self):
        # Slip period 2026-02, matched to a bank Gaji credit dated 2026-03.
        credits = [_credit("Gaji", 8_000_000, "2026-03-25")]
        slips = [_slip("slip.pdf", total_paid=7_250_000, deduction=750_000,
                       period="2026-02")]
        matches = [_match("slip.pdf", "2026-03")]
        rows = build_monthly_breakdown(credits, slips, matches)
        self.assertEqual([r.month for r in rows], ["2026-03"])    # not 2026-02
        r = rows[0]
        self.assertEqual(r.source, "bank_verified")
        self.assertEqual(r.deduction, 750_000)

    def test_rows_sorted_ascending(self):
        credits = [_credit("Gaji", 1, "2026-03-25"),
                   _credit("Gaji", 1, "2026-01-25")]
        rows = build_monthly_breakdown(credits, slip_docs=[], matches=[])
        self.assertEqual([r.month for r in rows], ["2026-01", "2026-03"])

    def test_multiple_slips_same_month_sum(self):
        slips = [
            _slip("a.pdf", total_paid=1_000_000, deduction=100_000, period="2026-05"),
            _slip("b.pdf", total_paid=2_000_000, deduction=200_000, period="2026-05"),
        ]
        rows = build_monthly_breakdown(credits=[], slip_docs=slips, matches=[])
        r = _by_month(rows)["2026-05"]
        self.assertEqual(r.deduction, 300_000)
        self.assertEqual(r.total_paid, 3_000_000)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_monthly.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ocr_orchestrator.monthly'`.

- [ ] **Step 3: Implement `ocr_orchestrator/monthly.py`**

Create `ocr_orchestrator/monthly.py`:

```python
"""Pure per-month income breakdown (spec §4–§6).

Joins the mutasi ``credits[]`` and slip ``documents[]`` the pipeline already
fetched, keyed by month, into one ``MonthlyIncomeRow`` per month (union of bank
salary-credit months and slip-period months). Bank-first: bank credits are the
source of truth for the income amounts; the matched slip supplies
``deduction``/``total_paid``. No I/O — mirrors ``income.py``/``verify.py``.

Reuses ``_slip_month`` from ``ocr_match.pipeline`` (the non-trivial month
derivation: slip ``period`` then filename parsing). Credit months are the same
``tanggal[:7]`` slice ``income.py`` uses.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from ocr_match.models import ParsedSlip
from ocr_match.pipeline import _slip_month

from .models import MonthlyIncomeRow

# Bank credit categories that count as salary-type (a row-creating signal).
# 'Lainnya' is excluded — it never creates a month on its own (spec §6).
_FIXED = "Gaji"
_THR = "THR"
_NON_FIXED = ("Bonus", "Insentif")
_SALARY_TYPE = (_FIXED, _THR) + _NON_FIXED


def _f(value: Any) -> float:
    """Coerce a possibly-None/str amount to float; None -> 0.0."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _credit_month(tanggal: Any) -> Optional[str]:
    """Same slice income.py uses: ISO 'YYYY-MM-DD' -> 'YYYY-MM'."""
    if isinstance(tanggal, str) and len(tanggal) >= 7:
        return tanggal[:7]
    return None


def build_monthly_breakdown(
    credits: list[dict[str, Any]],
    slip_docs: list[dict[str, Any]],
    matches: list,
) -> list[MonthlyIncomeRow]:
    """Build the per-month income table (spec §6).

    Args:
        credits: every mutasi credit dict (all categories) with ``category``,
            ``amount``, ``tanggal`` (ISO ``YYYY-MM-DD``).
        slip_docs: ocr_slip ``documents[]`` dicts.
        matches: ``ocr_match.models.MatchPair`` list from the verify stage. Only
            ``pair.slip.source_file`` and ``pair.credit.month`` are read.

    Returns:
        ``MonthlyIncomeRow`` list sorted ascending by ``month``.
    """
    # --- bank side: sum salary-type credits per month -----------------------
    bank: dict[str, dict[str, float]] = {}
    for c in credits:
        category = c.get("category")
        if category not in _SALARY_TYPE:
            continue                       # 'Lainnya'/None never create a month
        month = _credit_month(c.get("tanggal"))
        if not month:
            continue
        b = bank.setdefault(month, {"gaji": 0.0, "thr": 0.0, "bonus": 0.0})
        amount = _f(c.get("amount"))
        if category == _FIXED:
            b["gaji"] += amount
        elif category == _THR:
            b["thr"] += amount
        else:                              # Bonus or Insentif
            b["bonus"] += amount

    # --- which slips matched, and to which bank month -----------------------
    matched_home: dict[str, str] = {}      # slip source_file -> bank credit month
    for pair in matches:
        source_file = pair.slip.source_file
        credit_month = pair.credit.month
        if source_file and credit_month:
            matched_home[source_file] = credit_month

    # --- slip side: home each slip and accumulate ---------------------------
    slip: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"deduction": 0.0, "total_paid": 0.0,
                 "pokok": 0.0, "incentive": 0.0, "matched": False}
    )
    for d in slip_docs:
        source_file = d.get("source_file")
        if source_file in matched_home:
            home = matched_home[source_file]
            is_matched = True
        else:
            home = _slip_month(ParsedSlip(**d))
            is_matched = False
        if not home:
            continue                       # un-placeable slip (no month) is dropped
        s = slip[home]
        s["deduction"] += _f(d.get("deduction"))
        s["total_paid"] += _f(d.get("total_paid"))
        s["pokok"] += _f(d.get("pokok"))
        s["incentive"] += _f(d.get("incentive"))
        s["matched"] = s["matched"] or is_matched

    # --- assemble one row per month (union), sorted -------------------------
    rows: list[MonthlyIncomeRow] = []
    for month in sorted(set(bank) | set(slip)):
        b = bank.get(month)
        s = slip.get(month)
        if b is not None:
            # bank row: bank-sourced fields are real sums (0 when absent)
            if s is not None:
                source = "bank_verified" if s["matched"] else "bank_unverified"
                deduction = s["deduction"]
                total_paid = s["total_paid"]
            else:
                source = "bank_only"
                deduction = None
                total_paid = None
            rows.append(MonthlyIncomeRow(
                month=month,
                fixed_routine_income=b["gaji"],
                thr=b["thr"],
                bonus_non_fixed=b["bonus"],
                deduction=deduction,
                total_paid=total_paid,
                bank_salary_credit=b["gaji"],
                source=source,
            ))
        else:
            # slip_only row: no bank data -> thr / bank_salary_credit null
            rows.append(MonthlyIncomeRow(
                month=month,
                fixed_routine_income=s["pokok"],
                thr=None,
                bonus_non_fixed=s["incentive"],
                deduction=s["deduction"],
                total_paid=s["total_paid"],
                bank_salary_credit=None,
                source="slip_only",
            ))
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/Scripts/python -m pytest ocr_orchestrator/tests/test_monthly.py -v
```
Expected: PASS — all 11 tests green.

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/monthly.py ocr_orchestrator/tests/test_monthly.py
git commit -m "feat(orchestrator): per-month income breakdown join (monthly.py)"
```

---

## Task 3: Wire the breakdown into the pipeline

**Files:**
- Modify: `ocr_orchestrator/pipeline.py` (imports + aggregate stage, around lines 14-26 and 184-197)
- Test: `ocr_orchestrator/tests/test_pipeline.py`

- [ ] **Step 1: Extend the end-to-end test**

In `ocr_orchestrator/tests/test_pipeline.py`, add these assertions to the **end** of the existing `test_happy_path_bank_verified` method (it already produces one Gaji credit in 2025-03 matched to a 2025-02 slip → one `bank_verified` row):

```python
        # --- monthly breakdown is populated end-to-end ---
        breakdown = job.result.income.monthly_breakdown
        self.assertEqual(len(breakdown), 1)
        row = breakdown[0]
        self.assertEqual(row.month, "2025-03")          # homed to the bank credit month
        self.assertEqual(row.source, "bank_verified")
        self.assertEqual(row.fixed_routine_income, 9_500_000)
        self.assertEqual(row.bank_salary_credit, 9_500_000)
        self.assertEqual(row.total_paid, 9_500_000)     # from the matched slip
        self.assertEqual(row.thr, 0.0)                  # bank row, no THR -> real 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_pipeline.py::TestRunJob::test_happy_path_bank_verified" -v
```
Expected: FAIL — `assertEqual(len(breakdown), 1)` fails because `monthly_breakdown` is still its default `[]`.

- [ ] **Step 3: Wire `build_monthly_breakdown` into the aggregate stage**

In `ocr_orchestrator/pipeline.py`, add the import next to the other local imports (the block importing `from .income import compute_income`):

```python
from .monthly import build_monthly_breakdown
```

In the `# ---- Stage 4: aggregate ----` block, immediately **after** the `income = compute_income(...)` call and **before** `timings["aggregate"] = ...`, add:

```python
    income.monthly_breakdown = build_monthly_breakdown(credits, slip_docs, matches)
```

`credits`, `slip_docs`, and `matches` are all already in scope at that point (`credits` from the extract stage, `slip_docs` from the extract stage, `matches` from the verify stage). `compute_income` always returns an `IncomeBreakdown` (never `None`), and the model is mutable, so the assignment is safe.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
.venv/Scripts/python -m pytest "ocr_orchestrator/tests/test_pipeline.py::TestRunJob::test_happy_path_bank_verified" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ocr_orchestrator/pipeline.py ocr_orchestrator/tests/test_pipeline.py
git commit -m "feat(orchestrator): attach monthly_breakdown in the aggregate stage"
```

---

## Task 4: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole orchestrator suite**

Run:
```bash
.venv/Scripts/python -m pytest ocr_orchestrator/tests -v
```
Expected: PASS — every test, including the pre-existing ones (the change is purely additive; `income.py`, `verify.py`, and the aggregate math are untouched).

- [ ] **Step 2: Confirm the response schema renders**

Sanity-check that the new field serializes (the orchestrator's OpenAPI/`JobStatusResponse` picks it up via `IncomeBreakdown`):

```bash
.venv/Scripts/python -c "from ocr_orchestrator.models import IncomeBreakdown, MonthlyIncomeRow; print('monthly_breakdown' in IncomeBreakdown.model_fields)"
```
Expected output: `True`

- [ ] **Step 3: Final commit (if anything was left uncommitted)**

```bash
git status
# working tree should be clean; if not, review and commit code-only changes
```

---

## Self-Review (author check — completed)

**Spec coverage:**
- §4 schema (`MonthlyIncomeRow`, `RowSource`, `monthly_breakdown` field) → Task 1.
- §5 new pure module `monthly.py` + helper reuse → Task 2 (Step 3).
- §6 join algorithm — bank grouping, slip homing (matched→credit month, unmatched→slip period), union+sort, source flags, 0-vs-null, Lainnya excluded, Insentif→non-fixed, multi-slip sum → Task 2 tests (Step 1) + impl (Step 3).
- §7 wiring in aggregate stage → Task 3.
- §8 testing (new `test_monthly.py` per source flag + edges; extend `test_pipeline.py`) → Tasks 2 & 3; full-suite run → Task 4.
- §9 out of scope — no `income.py` math change, no new stage/upstream call → honored (aggregate stage only mutates `income.monthly_breakdown`).

**Placeholder scan:** none — every code/test step shows complete code and exact commands.

**Type consistency:** `MonthlyIncomeRow` field names and `RowSource` literals are identical across Task 1 (model), Task 2 (constructor calls + assertions), and Task 3 (assertions). `build_monthly_breakdown(credits, slip_docs, matches)` signature matches its call site in `pipeline.py`. Reused helper `_slip_month` and model `ParsedSlip` match their real definitions in `ocr_match`.
