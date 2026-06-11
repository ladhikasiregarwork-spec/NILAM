# Orchestrator — Per-Month Income Breakdown — Design Spec

**Date:** 2026-06-11
**Status:** ✅ Implemented (shipped to `main`, 2026-06-11)
**Scope:** `ocr_orchestrator` output only — one additive table. No new upstream
calls, no new stage, no decision/FMV logic.

---

## 1. Purpose

Today `ocr_orchestrator` returns income as a single **aggregate** figure
(`IncomeBreakdown`: `avg_monthly_gaji_insentif`, `monthly_thr`, `bonus_total`,
`monthly_qualifying_income`, `basis`, …). Analysts also want to see the
**per-month detail** behind that figure.

This spec adds a per-month table to the orchestrator's final result. Each row
covers one calendar month and reports seven fields the analyst asked for:

> **month payment**, **fixed routine income**, **THR**, **Bonus / non-fixed
> income**, **deduction**, **total paid**, **bank salary credit amount**.

The aggregate fields are **unchanged**; this table is purely additive.

---

## 2. What already exists (the data sources)

| Source | Module | Per-record fields used |
|---|---|---|
| Salary slip | `ocr_slip` `documents[]` | `pokok`, `incentive`, `deduction`, `total_paid`, `period` |
| Bank statement | `ocr_mutasi` `credits[]` | `category` ∈ {Gaji, THR, Bonus, Insentif, Lainnya}, `amount`, `tanggal` |
| Slip↔Gaji matches | `verify` stage → `ocr_match` `MatchPair[]` | `slip`, `credit`, X+1 payroll-lag aware month |

**The constraint that shapes this design:** the two sources do not overlap.

- `deduction` and `total_paid` exist **only on the slip**.
- The `THR` / `Bonus` / `Insentif` split exists **only on the bank statement** —
  the slip merges all of them into one `incentive` number.
- `bank salary credit amount` is bank-only.

So every monthly row is a **join** of slip data and bank data. The orchestrator
already fetches all three sources and the `verify` stage already produces the
`MatchPair[]` that bridges them.

---

## 3. Key decisions (from brainstorming)

1. **Bank-first, slip fills gaps.** Bank credits are the source of truth for the
   income amounts (the only place THR/Bonus/Insentif are separated); the matched
   slip supplies `deduction` and `total_paid`. Consistent with the existing
   income engine, which already treats the bank as source of truth.
2. **Union of months.** A row is emitted for every month seen in **either** a
   bank salary-type credit **or** a slip period. Half-empty rows are expected.
3. **Null missing + per-row `source` flag.** Missing fields are `null` (never
   `0` — `0` must mean a real zero). Every row carries a `source` flag so the gap
   is explicit and auditable.
4. **Insentif → non-fixed.** `fixed_routine_income = Gaji`;
   `bonus_non_fixed = Bonus + Insentif`; `Lainnya` ignored. **This intentionally
   differs** from the existing aggregate, which counts Insentif **as salary**
   (`avg_monthly(Gaji + Insentif)`). The two views serve different purposes (a
   lending qualifying-income calc vs. a per-category monthly detail) and are
   allowed to differ. Documented in §7 and in the `monthly.py` docstring so it is
   not later "fixed" as a bug.
5. **THR / Bonus are raw, not amortized.** They appear at their **actual amount
   in the month they landed** (e.g. THR 8.0M in 2026-04). The `÷12` amortization
   stays in the aggregate only.
6. **"month payment" = the month key** (`YYYY-MM`). The six amounts are the
   other fields.
7. **Approach A — new pure module.** Logic lives in a new
   `ocr_orchestrator/monthly.py`, mirroring `income.py` / `verify.py` (small,
   pure, no I/O, independently unit-testable). `income.py` is untouched.
8. **Output nested under `income`.** The table is `income.monthly_breakdown`, so
   all income data stays in one object.

---

## 4. Schema

New model + one new field, in `ocr_orchestrator/models.py`:

```python
RowSource = Literal["bank_verified", "bank_unverified", "bank_only", "slip_only"]

class MonthlyIncomeRow(BaseModel):
    """One calendar month of income, joined from bank credits + a salary slip."""
    month: str                              # "YYYY-MM" — the "month payment" key
    fixed_routine_income: Optional[float]   # bank Gaji   (slip pokok if slip_only)
    thr: Optional[float]                    # bank THR    (null if slip_only)
    bonus_non_fixed: Optional[float]        # bank Bonus + Insentif (slip incentive if slip_only)
    deduction: Optional[float]              # slip only
    total_paid: Optional[float]             # slip only
    bank_salary_credit: Optional[float]     # bank Gaji credit amount (null if slip_only)
    source: RowSource

class IncomeBreakdown(BaseModel):
    ...                                     # all existing aggregate fields unchanged
    monthly_breakdown: list[MonthlyIncomeRow] = Field(default_factory=list)
```

`IncomeBreakdown` already has a `monthly_breakdown` default of `[]`, so existing
consumers and tests that ignore the field are unaffected.

---

## 5. New module — `ocr_orchestrator/monthly.py`

```python
def build_monthly_breakdown(
    credits: list[dict],        # every mutasi credit (all categories)
    slip_docs: list[dict],      # ocr_slip documents[]
    matches: list,              # MatchPair[] produced by the verify stage
) -> list[MonthlyIncomeRow]: ...
```

Pure function, no I/O. Reuses `_credit_month` / `_slip_month` from
`ocr_match.pipeline` (the same helpers `verify.py` already imports) so month
derivation cannot drift between the verify stage and this table. Constructs
`ParsedSlip` / `GajiCredit` from the raw dicts the same way `verify.py` does.

---

## 6. The join algorithm

1. **Group bank credits by month** (`_credit_month`). Per month, sum by category:
   - `fixed_routine_income` ← Σ `Gaji`
   - `bank_salary_credit`   ← Σ `Gaji`  (the raw Gaji credit total that month)
   - `thr`                  ← Σ `THR`
   - `bonus_non_fixed`      ← Σ (`Bonus` + `Insentif`)
   - `Lainnya` ignored.
2. **Home each slip to a month:**
   - matched slip → its matched **bank credit's** month (absorbs the X+1 lag).
   - unmatched slip → its own **slip-period** month (`_slip_month`).
   Attach that slip's `deduction` + `total_paid` to the homed month. If more than
   one slip homes to the same month, sum `deduction` and `total_paid`.
3. **Union the month keys** from steps 1 & 2; emit one row each, **sorted
   ascending by month**.
4. **Per-row `source`** (first match wins):
   - a **matched** slip is homed here → `bank_verified`
   - bank credits present **and** an unmatched slip homed here → `bank_unverified`
   - bank credits present, no slip homed here → `bank_only`
   - no bank credits, slip only → `slip_only`
5. **Field values per row type — the `0`-vs-`null` rule:**
   - **Bank rows** (`bank_verified` / `bank_unverified` / `bank_only`): every
     bank-sourced field is a **category sum**, so it is a real **`0`** when that
     category had no credit that month (the statement *did* cover the month —
     e.g. a normal no-THR month shows `thr = 0`, not `null`). `deduction` and
     `total_paid` come from the homed slip, or **`null`** if no slip homed here.
   - **`slip_only` rows**: `fixed_routine_income` ← `pokok`,
     `bonus_non_fixed` ← `incentive`, `deduction`/`total_paid` from the slip;
     `thr` = **`null`** and `bank_salary_credit` = **`null`** (no bank data — the
     slip cannot split THR, and there is no credit).
6. **`null` means "no data source for this field"; `0` means "a source covered
   it and the amount was zero."** They are never interchangeable.

### Worked example

Bank statement spans 2026-01…2026-04 (a `Gaji` credit each month; a `Bonus` of
1.5M in 2026-03; a `THR` of 8.0M in 2026-04). Slips uploaded for 2026-01..2026-03
matched to those months (each `pokok` 6.5M, `incentive` 1.5M, `deduction` 0.75M,
`total_paid` 7.25M); no slip for 2026-04; one extra slip for 2026-05 with no bank
coverage. *(Matching shown same-month for readability; with the X+1 payroll lag a
slip for period X homes into its matched credit's month X+1 — step 2.)*

| month | fixed | thr | bonus_non_fixed | deduction | total_paid | bank_salary_credit | source |
|---|---|---|---|---|---|---|---|
| 2026-01 | 8.0M | 0 | 0 | 0.75M | 7.25M | 8.0M | bank_verified |
| 2026-02 | 8.0M | 0 | 0 | 0.75M | 7.25M | 8.0M | bank_verified |
| 2026-03 | 8.0M | 0 | 1.5M | 0.75M | 7.25M | 8.0M | bank_verified |
| 2026-04 | 8.0M | 8.0M | 0 | null | null | 8.0M | bank_only |
| 2026-05 | 6.5M | null | 1.5M | 0.75M | 7.25M | null | slip_only |

Note the contrast: `thr` is `0` on the bank-backed months (statement covered them,
no THR credit) but `null` on the `slip_only` row (no bank data to know).
`deduction`/`total_paid` are `null` on the `bank_only` month (no slip uploaded).
A `bank_unverified` row (bank credits present + a slip that did **not**
amount-match) is not shown but follows the same bank-row rules, with the
unmatched slip's `deduction`/`total_paid` still attached.

---

## 7. Wiring — `pipeline.py`, aggregate stage

Inside the existing stage-4 block, immediately after `compute_income(...)`:

```python
income.monthly_breakdown = build_monthly_breakdown(credits, slip_docs, matches)
```

`credits`, `slip_docs`, and `matches` are all already in scope at that point.
No new upstream call, no new stage, and no signature change to `compute_income`
or `verify_slips_credits`. `IncomeBreakdown` is mutable (pydantic default), so
attribute assignment is valid; `compute_income` returns it with the field at its
`[]` default.

---

## 8. Testing

- **New `ocr_orchestrator/tests/test_monthly.py`** (mirrors `test_income.py`
  style — plain `unittest`, small credit/slip dict fixtures):
  - one test per `source` flag (`bank_verified`, `bank_unverified`, `bank_only`,
    `slip_only`);
  - X+1 lag homing (slip period X → matched credit month X+1 → both in the X+1 row);
  - THR-only / Bonus-only month;
  - Insentif folded into `bonus_non_fixed`;
  - `null` vs `0` discipline (missing field is `null`; a real zero stays `0`);
  - empty inputs → `[]`;
  - rows sorted ascending by month;
  - multiple slips homing to one month sum `deduction`/`total_paid`.
- **Extend `tests/test_pipeline.py`** to assert `income.monthly_breakdown` is
  populated and correctly shaped end-to-end.

Run from the repo root:

```
.venv/Scripts/python -m pytest ocr_orchestrator/tests -v
```

---

## 9. Out of scope

- No new fields on KTP/KK (still classified, not extracted).
- No FMV, no approve/reject decision, no frontend wiring.
- No change to the aggregate qualifying-income math in `income.py`.
- No new upstream service calls or new pipeline stage.
