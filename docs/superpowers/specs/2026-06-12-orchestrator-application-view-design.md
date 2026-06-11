# Orchestrator: UI-shaped `ApplicationView` (assessment dashboard data contract)

**Date:** 2026-06-12
**Status:** 📝 Draft (design approved in brainstorming; spec under review)
**Scope:** Extend `ocr_orchestrator` to (a) accept the KPR assessment dashboard's user
inputs and (b) serve a single **UI-shaped `ApplicationView`** covering every in-scope
dashboard section. Derived from the screenshots in `ui_ss/`. The domain pipeline
(classify → extract → acquire → aggregate → fmv → decide) is **unchanged**; this adds
a request extension plus a **pure projection layer (`view.py`)**.

---

## 1. Purpose

The dashboard (see `ui_ss/`) renders one applicant's full picture: uploaded documents,
identity (KTP/KK), employment, collateral + NPW, income/installment affordability,
slip↔mutasi matching, and the bank statement. The orchestrator already computes the hard
parts (income, FMV, decision, verification, monthly breakdown, slip/mutasi extraction).

This spec makes the orchestrator the **single front door for the dashboard**: it receives
the user inputs and returns **one self-contained read-model** the frontend renders section
by section — no client-side stitching across services.

**Out of scope (separate, later):** credit scoring, SLIK OJK, document preview, and
persisting an application file. The assumption "we can get most of all information" means
identity (KTP/KK) fields are defined in the contract now and filled by a future extractor.

---

## 2. UI → data-source map

| Dashboard section | Source | Status |
|---|---|---|
| **Data Already Upload** (5 doc chips) | `ApplicationResult.documents[]` | ✅ reuse |
| **User Information** → KTP | `ApplicantInfo` (name real; nik/dob/age/gender stub) | 🟡 contract-now |
| **User Information** → KK | future KK extractor (stub) | 🟡 contract-now |
| **Company Employment Certificate** | project from `ocr_sk` (`sk_response`) | 🟢 new projection, real data |
| **NPW & Informasi Agunan** | echoed inputs + `npw = fmv.fair_value` | 🟢 new block |
| **Perhitungan Agunan** (LTV, Plafon, Kebutuhan) | **frontend-computed**; backend serves only NPW | — (NPW only) |
| **Calculate Installment / Kemampuan Bayar** | `IncomeBreakdown` + `DecisionResult` | 🟢 new projection |
| **Matching Slip ↔ Mutasi** → transaksi pemasukan | mutasi `credits[]` (classified) | ✅ reuse |
| **Matching** → rekap per bulan | projector joins slips + credits + matches | 🟢 new (D4) |
| **Matching** → salary slip table | slip extraction (`slip_docs`) | ✅ reuse |
| **Bank Statement** | classified credits + totals (debits deferred) | 🟡 D5 |
| **Decision** | `DecisionResult` | ✅ reuse |
| ~~Credit Scoring / SLIK OJK / Preview Dokumen~~ | — | ⛔ out of scope |

---

## 3. Decisions (confirmed in brainstorming)

- **Architecture:** single `ApplicationView` assembled by a pure `view.py` projector; the
  domain `ApplicationResult` stays the internal model (approach ①).
- **D1 — Installment served computed.** The orchestrator returns the computed income
  breakdown, Kemampuan Bayar, and Angsuran KPR (reuses `income.py` + `decision.py`). SLIK
  deduction is `0` for now (ignored).
- **D2 — Identity contract-now.** KTP/KK fields are defined in the response and returned as
  `null` placeholders (employment is real from `ocr_sk`); a future extractor fills them.
- **D3 — `loan_amount` derived.** The request carries `harga_rumah` + `dp`; the orchestrator
  computes `loan_amount = harga_rumah − dp` and feeds it to `decide`. `loan_amount` is no
  longer a request field (still echoed in the response).
- **D4 — Rekap per bulan = slip+mutasi split.** Computed in the projector (a new `RekapRow`),
  leaving the bank-first `MonthlyIncomeRow` untouched (per its "do not fix the divergence"
  contract).
- **D5 — Bank statement = classified credits + totals now.** The full debit-level ledger is
  deferred until `ocr_mutasi` exposes all rows (a separate, cross-service change).

---

## 4. Request contract — `POST /api/v1/applications` (multipart Form)

Unchanged: `files`, `bonus_accept_pct`, `password`, `luas_tanah`, `luas_bangunan`,
`kode_pos`, `kelurahan`, `appraisal_month`, `tenor_months`, `annual_interest_rate`.

**Added:** `provinsi`, `kota_kab`, `kecamatan` (agunan address, echoed for the view),
`harga_rumah`, `dp`.

**Removed as input:** `loan_amount` — derived as `harga_rumah − dp`.

Validation reuses the existing helpers (`> 0` / `>= 0` numeric checks, partial-group
warnings). Collateral still needs both `luas_tanah` + `luas_bangunan` to price FMV; the loan
path needs `harga_rumah`, `dp`, `tenor_months`, `annual_interest_rate`. Partial groups append
a warning and skip that stage (unchanged behavior).

---

## 5. Response contract — `ApplicationView`

`JobStatusResponse.result` becomes `Optional[ApplicationView]`. New view models live in
`models.py`; existing typed blocks are **reused as nested sub-objects** (single source of
truth — no duplication).

```text
ApplicationView
├─ documents:     list[DocumentResult]           # reuse
├─ identity:      IdentityView
│   ├─ ktp:  { nama, nik, gender, tgl_lahir, age }   # nama real; rest null (stub)
│   └─ kk:   { no_kk, kepala_keluarga, anggota[ {nama, nik} ] }   # stub
├─ employment:    EmploymentView | null          # from sk_response
│      { perusahaan, jabatan, status, masa_kerja, start_date }
├─ agunan:        AgunanView
│      { harga_rumah, luas_tanah, luas_bangunan,
│        provinsi, kota_kab, kecamatan, kelurahan, kode_pos,
│        npw,                       # = fmv.fair_value
│        fmv: FmvResult | null }    # land/building/location_matched detail (reuse)
├─ installment:   InstallmentView | null
│      { gaji_bulanan,        # = income.avg_monthly_gaji_insentif
│        thr_bulanan,         # = income.monthly_thr
│        bonus_bulanan,       # = income.bonus_monthly
│        bonus_total, bonus_accept_pct,
│        monthly_qualifying_income,   # = income.monthly_qualifying_income
│        slik_deduction,      # = 0 (decision.existing_installment)
│        kemampuan_bayar,     # = monthly_qualifying_income − slik_deduction
│        angsuran_kpr,        # = decision.monthly_installment
│        verdict }            # = decision.recommendation (drives the UI "KPR layak" badge)
├─ matching:      MatchingView
│   ├─ transaksi_pemasukan: list[CreditView]     # classified Gaji/THR/Bonus credits
│   ├─ rekap_per_bulan:     list[RekapRow]        # §6
│   └─ salary_slip:         list[SlipView]
│          { tgl_pembayaran, total_upah, potongan, thp, thr, bonus }
├─ bank_statement: BankStatementView
│      { klasifikasi: { gaji, thr, bonus, tunjangan_cuti },
│        total_kredit, total_debet, n_transaksi,
│        credits: list[CreditView] }              # debits deferred (D5)
├─ income:        IncomeBreakdown | null          # reuse (domain detail / transparency)
├─ verification:  VerificationInfo                # reuse
├─ decision:      DecisionResult | null           # reuse
└─ audit:         OrchestratorAudit               # reuse
```

`CreditView` = `{ tanggal, amount, category, keterangan, month }` projected from a mutasi
credit. `npw` is `null` when FMV is unavailable.

---

## 6. Rekap-per-bulan projection (the one genuinely new computation)

`RekapRow` reproduces the dashboard's slip-vs-mutasi comparison, keyed by `YYYY-MM`:

```text
RekapRow { bulan,
           gaji_slip,  gaji_mutasi,
           thr_slip,   thr_mutasi,
           bonus_slip, bonus_mutasi,
           income_slip, potongan,
           status }     # default "non-edited" (frontend may flip to "edited")
```

- **Mutasi side** (`*_mutasi`): sum `credits` by `month` and category — `Gaji → gaji_mutasi`,
  `THR → thr_mutasi`, `Bonus`(+`Insentif`) `→ bonus_mutasi`.
- **Slip side** (`*_slip`, `income_slip`, `potongan`): from `slip_docs`, homed to a month via
  the matched pair (`matches`) or the slip's own `period`. Intended semantics from the UI:
  `gaji_slip = THP`, `thr_slip = slip THR`, `income_slip = total_upah`, `potongan` =
  `income_slip − gaji_slip − thr_slip`.
- Unmatched slips still produce a row (preserves the existing unmatched-slip rule).

**Implementation note:** exact per-column arithmetic (especially `potongan`, and whether
`Insentif` folds into `bonus_slip`) is pinned during implementation against `ocr_slip`'s and
`ocr_mutasi`'s real field names; the structure and homing rule above are fixed.

---

## 7. Identity stub & employment projection

- **Employment** (`EmploymentView`) projects from the `ocr_sk` response already fetched in
  the extract stage — `perusahaan`, `jabatan`, `status`, `masa_kerja`, `start_date`. `null`
  when `ocr_sk` returned nothing / was unreachable.
- **Identity** (`IdentityView`): `ktp.nama` comes from the existing
  `resolve_applicant_name` (slip → mutasi → sk). Every other KTP/KK field is `null` now and
  documented as awaiting a future KTP/KK extractor (D2). The contract shape is stable so the
  frontend needs no change when those fields start populating.

---

## 8. Components & data flow

New/changed files in `ocr_orchestrator/` (domain pipeline logic untouched):

1. **`view.py` (new)** — `build_application_view(result, *, agunan_inputs, sk_response,
   slip_docs, credits, matches) → ApplicationView`. **Pure and total**: no I/O; missing
   inputs project to `null`, never raises. The only place the UI shape lives.
2. **`models.py`** — add `ApplicationView`, `IdentityView`, `EmploymentView`, `AgunanView`,
   `InstallmentView`, `RekapRow`, `CreditView`, `SlipView`, `BankStatementView`. Reuse
   `DocumentResult`, `FmvResult`, `IncomeBreakdown`, `DecisionResult`, `VerificationInfo`.
3. **`api.py`** — add the Form fields; compute `loan_amount = harga_rumah − dp`; thread the
   echoed agunan inputs through `run_job`; `JobStatusResponse.result: ApplicationView`.
4. **`pipeline.py`** — at the *assemble* stage, after the domain `ApplicationResult` is built,
   call `view.build_application_view(...)` (all inputs — `sk_response`, `slip_docs`, `credits`,
   `matches`, echoed agunan inputs — are already in scope there) and store the view.

```text
UI form ─POST─▶ api: loan_amount = harga_rumah − dp
        ▶ run_job ▶ classify ▶ extract(ocr_sk) ▶ acquire(ocr_match: slip+mutasi+match)
        ▶ aggregate(income) ▶ fmv ▶ decide ▶ assemble→ApplicationResult
        ▶ view.build_application_view ─▶ ApplicationView ─poll GET─▶ UI renders sections
```

---

## 9. Error handling & degradation

All reuse the existing pipeline behavior; the projector renders whatever exists:

- Classifier down → job `failed` (unchanged).
- `ocr_match` down → `installment` / `matching` empty; `agunan` + `fmv` + `decision` still
  render (degraded, job completes).
- FMV down → `agunan.npw = null` + warning; rest intact.
- `ocr_sk` down → `employment = null` + warning.
- Identity/KK always `null` now (documented stub).
- Because `view.py` is total, the response **always** assembles; the `run_job` backstop that
  converts unexpected exceptions into a failed job stays.

---

## 10. Testing

- **`view.py` unit tests** per section: employment from a sample `sk_response`;
  `agunan.npw == fmv.fair_value`; installment from `income` + `decision`; rekap split from
  sample slips + credits + matches (incl. an unmatched slip → its own row); bank-statement
  totals.
- **`api.py`**: new Form fields parse; `loan_amount == harga_rumah − dp`; partial agunan/loan
  groups append warnings.
- **Degradation test**: `ocr_match` raises → view renders with empty installment/matching but
  populated agunan/fmv/decision.
- Domain tests (`income`, `monthly`, `decision`, `pipeline`) stay green; the few that read the
  old result shape are repointed to `ApplicationView`.

---

## 11. Out of scope

- Credit scoring, SLIK OJK, document preview, and saving an application file (each its own
  later spec).
- Real KTP/KK extraction (D2 stub now; future extractor service).
- The full debit-level bank ledger (D5 — needs an `ocr_mutasi` passthrough change).
- Frontend rendering / the Perhitungan Agunan LTV·Plafon math (frontend-owned).
