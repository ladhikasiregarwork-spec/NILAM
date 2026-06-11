# Orchestrator: single front door — slip + mutasi + match via `ocr_match`

**Date:** 2026-06-11
**Status:** ✅ Implemented (shipped to `main`, 2026-06-11)
**Scope:** `ocr_orchestrator` consumes an extended `ocr_match` response that carries
**full slip extraction + full mutasi extraction + the match result**, so the
orchestrator drops its own `ocr_slip` and `ocr_mutasi` calls entirely. Requires a
contract change in `ocr_match` (passthrough of the two upstream payloads).

---

## 1. Purpose

Today the orchestrator calls `ocr_slip`, `ocr_mutasi`, **and** imports `ocr_match`'s
matcher in-process. We collapse the slip + mutasi + match work into **one HTTP call
to `ocr_match`**:

- **Decouple (A):** no `ocr_match` imports, no shared venv, no `AZURE_OPENAI_*`
  requirement in the orchestrator.
- **Single front door (B):** `ocr_match` already runs `ocr_slip` and `ocr_mutasi`
  internally. If it **returns their full output** (not just the matched `Gaji`
  rows), the orchestrator needs no upstream extraction calls of its own — slips and
  mutasi are parsed **once**, inside `ocr_match`.

Classification (`ocr_classifier`, to know which PDFs are slips vs mutasi vs sk) and
the employment-letter call (`ocr_sk`) stay in the orchestrator. Only slip + mutasi +
match collapse into the `ocr_match` call.

---

## 2. Constraint reversal

The previous draft assumed `ocr_match` could not be modified and returned `Gaji`
credits only. **That is reversed:** `ocr_match` **will be extended** to (a) stop
discarding non-`Gaji` credits and (b) pass through the full slip and mutasi upstream
payloads. The orchestrator design below depends on that change shipping in
`ocr_match` first.

---

## 3. Required `ocr_match` response contract (`POST /api/v1/match`)

Three blocks: full **slip extraction**, full **mutasi extraction** (all categories +
account/files), and the **match result**. The two extraction blocks are the verbatim
upstream payloads — maximal passthrough, minimal translation, consistent with
`ocr_match`'s existing `extra="allow"` philosophy.

```jsonc
{
  // ── 1. SLIP EXTRACTION — verbatim ocr_slip /parse response body ──
  //    Every slip appears here, matched or not (slips can be > 1).
  "slip_extraction": {
    "documents": [
      {
        "source_file": "string",        // REQUIRED — per-doc key + name resolution
        "worker_name": "string|null",   // applicant-name resolution
        "institution_name": "string|null",
        "total_paid": 0.0,              // income slip_fallback + breakdown
        "pokok": 0.0,                   // breakdown (slip_only rows)
        "tax": 0.0,
        "incentive": 0.0,               // breakdown (slip_only rows)
        "deduction": 0.0,               // breakdown
        "other_deduction": 0.0,
        "period": "YYYY-MM|null",       // month placement for UNMATCHED slips
        "confidence_notes": [],
        "extraction_method": "string"
      }
    ]
  },

  // ── 2. MUTASI EXTRACTION — verbatim ocr_mutasi extract-batch response body ──
  //    credits[] MUST be ALL categories, not Gaji-only.
  "mutasi_extraction": {
    "files": [
      {
        "filename": "string",           // REQUIRED — per-doc attachment key
        "account": { "nama": "string|null" }   // REQUIRED — name fallback (passthrough rest)
      }
    ],
    "credits": [
      {
        "source_file": "string",
        "tanggal": "YYYY-MM-DD",        // REQUIRED — month derivation for income
        "amount": 0.0,                  // REQUIRED — income sums
        "category": "Gaji|Insentif|THR|Bonus|Lainnya",  // REQUIRED — NOT Gaji-only
        "keterangan": "string",
        "type": "CR", "saldo": null, "cbg": null, "page": 0,
        "confidence": null, "reason": null
      }
    ],
    "audit": {}                         // optional passthrough
  },

  // ── 3. MATCH RESULT — slip ↔ Gaji pairing (one entry per matched slip) ──
  "matches": [
    {
      "slip":   { "source_file": "string" },          // ≥ source_file
      "credit": { "month": "YYYY-MM", "tanggal": "YYYY-MM-DD", "amount": 0.0 },
      "match_pattern": "next_month|same_month|future_month|amount_only"
    }
  ],

  "audit": { "slip_count": 0, "credit_count": 0, "matched_count": 0,
             "months_processed": [], "matcher_errors": [], "upstream_errors": [] }
}
```

### 3.1 The two fields the current `ocr_match` does NOT provide

1. **`mutasi_extraction.credits[]` must include ALL categories.** Today
   `ocr_match/upstream.py:119` does `... if c.get("category") == "Gaji"`. The
   orchestrator income formula needs `Insentif`, `THR`, `Bonus`:
   `income = avg(Gaji+Insentif)/mo + THR/12 + Bonus*pct/12`. Drop the filter.
2. **`mutasi_extraction.files[].account.nama`** — applicant-name fallback (slip →
   mutasi → sk) and the per-document attachment key.

Everything else `ocr_match` already computes; it only needs to **stop discarding**
the two upstream payloads and return them.

---

## 4. `ocr_match` changes required (separate, must ship first)

- `ocr_match/upstream.py` — `extract_mutations` must return the **full**
  extract-batch payload (`files`, all-category `credits`, `audit`), not the
  `Gaji`-filtered `GajiCredit[]`. Likewise surface the full `ocr_slip` `documents`.
- `ocr_match/pipeline.py` / `models.py` — extend `MatchResponse` with
  `slip_extraction` and `mutasi_extraction` blocks (verbatim passthrough). The
  internal matcher still filters to `Gaji` for pairing; that's independent of what
  the response carries.
- No change to `ocr_slip` / `ocr_mutasi` themselves.

*(This section is the `ocr_match` contract requirement. A full `ocr_match`
implementation plan is its own task; this spec owns only the orchestrator side and
the contract it depends on.)*

---

## 5. Orchestrator changes

| File | Change |
|---|---|
| `upstream.py` | **Add** `match_documents(slip_pdfs, mutasi_pdfs, *, password)` → `POST {ocr_match_url}/api/v1/match`, returns parsed JSON; raises existing `Upstream*Error`. **Delete** `parse_slips` and `extract_mutations` outright (D1 — no fallback). |
| `verify.py` → match adapter | `MatchResponse` JSON → `(slip_docs, credits, mut_files, matches: list[MatchView], verified_months)`. No `ocr_match` imports. |
| `models.py` | local `MatchView` (`.slip.source_file`, `.credit.month/tanggal/amount`, `.match_pattern`). |
| `slip_dates.py` (new) | local `_slip_month` / `_credit_month` (pure date helpers, copied from `ocr_match.pipeline`) — used only to place **unmatched** slips. |
| `monthly.py` | drop `ocr_match` imports; use `slip_dates._slip_month`, iterate `MatchView`; `slip_docs`/`credits` stay plain dicts. |
| `pipeline.py` | restructure stages (§6): extract = `ocr_sk` only; new **acquire** stage replaces extract-of-slip/mutasi + verify; attach slip/mutasi to `doc_results` after it. |
| `config.py` | add `ocr_match_url` (`…:5005`) + `match_timeout_s` (generous — full OCR+LLM). Drop the `AZURE_OPENAI_*` note. **Remove** `ocr_slip_url` / `ocr_mutasi_url` — no longer consumed (D1). |

The data the adapter extracts maps 1:1 onto today's consumers, unchanged:
- `credits` ← `mutasi_extraction.credits` → `compute_income`, `build_monthly_breakdown`
- `slip_docs` ← `slip_extraction.documents` → `slip_total_paids`, breakdown, name
- `mut_files` ← `mutasi_extraction.files` → `doc_results` attach + `account.nama` name
- `matches` / `verified_months` ← `matches` → verification + breakdown homing

---

## 6. Pipeline stages

| # | Stage | Change |
|---|---|---|
| 1 | classify | unchanged → buckets (slips, mutasi, sk, ktp, kk) |
| 2 | extract | **`ocr_sk` only** now (slip + mutasi removed from here) |
| 3 | acquire (was *verify*) | one `ocr_match` call → `slip_docs`, `credits`, `mut_files`, `matches`, `verified_months`; then attach slip + mutasi onto `doc_results` |
| 4 | aggregate | unchanged logic; inputs now all come from stage 3 |
| 5 | fmv | unchanged |
| 6 | decide | unchanged |
| 7 | assemble | unchanged; name resolution reads stage-3 `slip_docs` + `mut_files[].account` |

`ocr_sk` (stage 2) and the `ocr_match` call (stage 3) are independent and may run
concurrently later; kept as distinct tracked stages here for clarity.

---

## 7. Multiple slips & the unmatched-slip rule

Slips (and mutasi files) can be many; the response arrays carry N of each, each slip
keyed by `source_file`. Matching is per-slip; the breakdown aggregates **by month**
(two slips in one month sum into one row; slips across months yield separate rows).

**Decision (confirmed): unmatched slips still contribute** — a slip with a derivable
month (`period` → filename) creates a `slip_only`, unverified month row even when no
bank `Gaji` credit pairs with it. This is preserved precisely because `ocr_match`
returns **every** slip in `slip_extraction.documents`, not just the matched ones.

---

## 8. Degrade behavior on `ocr_match` outage (decided: D1)

The single front door makes `ocr_match` carry slips **and** mutasi **and** matching,
so an `ocr_match` outage loses *all* income inputs at once. **Decision: D1 — degrade
to no-income, the job still completes.**

- On `UpstreamUnreachableError` / `UpstreamHttpError` from `match_documents`: the
  acquire stage logs it, appends a warning to `audit`, sets `slip_docs=[]`,
  `credits=[]`, `mut_files=[]`, `matches=[]`, `verified_months=∅`, and marks the
  stage `completed` (degraded, not failed).
- `compute_income` then yields `basis="none"` with a warning; FMV and decide still
  run on whatever inputs exist. Only the classifier stage fails a job; the `run_job`
  backstop still converts any *unexpected* exception into a failed job.
- The orchestrator keeps **no** `ocr_slip` / `ocr_mutasi` fallback clients — they are
  removed entirely (§5). `ocr_match` is the sole source of slip + mutasi data.

---

## 9. Testing

- `test_upstream.py` — `match_documents`: success, unreachable, http-error.
- match-adapter test — sample response → `slip_docs` / `credits` / `mut_files` /
  `MatchView[]` / `verified_months`; `credit.month` fallback to `tanggal[:7]`;
  multiple slips incl. an unmatched one → `slip_only` row.
- `test_pipeline.py` — happy path (no `ocr_slip`/`ocr_mutasi` calls made); §8 D1
  degrade path (`match_documents` raises → job `completed`, `basis="none"`, warning).
- `test_monthly.py` — `MatchView` inputs; rows unchanged for equivalent data.
- `test_slip_dates.py` (new) — `_slip_month` / `_credit_month`.
- **Decoupling guard** — assert zero `import ocr_match` under `ocr_orchestrator/`.

---

## 10. Out of scope

- The `ocr_match` implementation itself (§4 is the contract; its build is a separate
  plan). Income formula, `fmv`, `decide`, `identity`, frontend — unchanged.
- Concurrency of `ocr_sk` vs the `ocr_match` call (§6).
