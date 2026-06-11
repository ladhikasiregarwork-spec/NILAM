# Orchestrator: route matching + slip extraction through the hosted `ocr_match` service

**Date:** 2026-06-11
**Status:** Approved (design); pending implementation plan
**Scope:** `ocr_orchestrator` only — replace the in-process matcher with an HTTP
call to the already-deployed `ocr_match` service. No change to `ocr_match` or any
other service.

---

## 1. Purpose

Today the orchestrator's **verify** stage matches salary slips against bank `Gaji`
credits by **importing `ocr_match`'s code in-process** (`ocr_orchestrator/verify.py`
does `from ocr_match.matcher import match_all`; `ocr_orchestrator/monthly.py` also
imports `ParsedSlip` and `_slip_month` from `ocr_match`).

This spec changes the orchestrator to call the **hosted `ocr_match` service over
HTTP** (`POST /api/v1/match`) instead. Two goals drive it:

- **Decouple the code (A):** the orchestrator should not import `ocr_match`, share
  its venv, or inherit its `AZURE_OPENAI_*` requirement. It should treat
  `ocr_match` as a true remote microservice.
- **Single source of truth (B):** all matching logic lives only in the deployed
  `ocr_match` service, so matching can change in one place.

A secondary win falls out of the change: because `ocr_match`'s response already
contains fully-parsed slip data, the orchestrator can **source its slip extraction
from `ocr_match`** and drop its own happy-path `ocr_slip` call — so slips are
parsed once, not twice.

---

## 2. Hard constraint: `ocr_match` cannot be modified

`ocr_match` is a fixed, already-deployed service. The only matching endpoint is
`POST /api/v1/match`, which takes **raw PDFs** (`slips` + `mutations` multipart
groups), parses them itself (calling `ocr_slip` and `ocr_mutasi`), runs the
matcher, and returns a `MatchResponse`. There is **no endpoint that accepts
already-parsed data**. Everything below is shaped by that.

### 2.1 What `/api/v1/match` returns (verified against `ocr_match` source)

`MatchResponse` =
- `matches[]` — each `MatchPair` carries a **full `ParsedSlip`** (`worker_name`,
  `institution_name`, `total_paid`, `pokok`, `tax`, `incentive`, `deduction`,
  `period`, `source_file`, …), a `GajiCredit`, `match_pattern`, `confidence`,
  `reason`, `amount_diff_*`.
- `unmatched_slips[]` — full `ParsedSlip` objects.
- `unmatched_credits[]` — `GajiCredit` objects.
- `audit` — `slip_count`, `credit_count`, `matched_count`, `months_processed`,
  `matcher_errors`, `upstream_errors`.

Every input slip appears exactly once across `matches[].slip ∪ unmatched_slips`,
so the **full slip set is recoverable** from one response.

### 2.2 The mutation caveat that shapes the design

`ocr_match.upstream.extract_mutations` ends with
`return [GajiCredit(**c) ... if c.get("category") == "Gaji"]` — it calls
`ocr_mutasi` with all categories internally but **discards everything except
`Gaji`** before returning. So `THR`, `Bonus`, `Insentif`, and `Lainnya` **never
appear** in the response.

The orchestrator's income formula (`ocr_orchestrator/income.py`) needs those other
categories:

```
monthly_qualifying_income
  = avg_monthly(Gaji + Insentif) over distinct salary months
  + total(THR)   / 12
  + total(Bonus) * bonus_accept_pct / 12
```

**Therefore:** `ocr_match` can replace the orchestrator's **slip** extraction but
**not** its mutasi extraction. The orchestrator must keep calling `ocr_mutasi`
itself to obtain the full all-category credit set.

---

## 3. Key decisions (from brainstorming)

1. **Approach: full decouple.** No `ocr_match` imports remain anywhere under
   `ocr_orchestrator/`. The JSON response is parsed into local types; the two pure
   date helpers are reimplemented locally.
2. **Slips sourced from `ocr_match`** in the happy path; the orchestrator's own
   `ocr_slip` call is removed from the extract stage.
3. **`ocr_slip` retained as a fallback-only call.** If `ocr_match` is unreachable
   or errors, the orchestrator calls `ocr_slip/parse` to recover slip data, so the
   `slip_fallback` income path (zero bank salary credits) and slip-based name
   resolution survive a matcher outage.
4. **Degrade, never fail, on `ocr_match` outage.** Matches become empty,
   `verified_months` empty, a warning is recorded in `audit`; income still computes
   from bank credits (`bank_unverified`) and the job completes.
5. **Mutasi double-parse is accepted.** Unavoidable while `ocr_match` is
   untouchable and income needs all categories. Slips are parsed once.

---

## 4. Revamped pipeline

`ocr_orchestrator/pipeline.py` stage flow (tracked stages in `job.stages` keep the
same names; **verify** is renamed **match**):

| # | Stage | Change |
|---|---|---|
| 1 | classify | unchanged — produces buckets (slips, mutasi, sk, ktp, kk) |
| 2 | extract | `ocr_mutasi` (all categories) + `ocr_sk` concurrently. **`ocr_slip` removed from this stage.** |
| 3 | match (was *verify*) | call `ocr_match`; on failure, fallback to `ocr_slip`. Produces `slip_docs`, `matches`, `verified_months`. |
| 4 | aggregate | unchanged logic; `slip_docs` now originates from stage 3 |
| 5 | fmv | unchanged |
| 6 | decide | unchanged |
| 7 | assemble | unchanged; applicant-name resolution reads `slip_docs` from stage 3 |

### 4.1 Match stage detail

```
slip_pdfs  = buckets.slips     # raw (filename, bytes) from classify
mutasi_pdfs = buckets.mutasi   # raw (filename, bytes) from classify

try:
    resp = await upstream.match_documents(slip_pdfs, mutasi_pdfs, password=password)
    slip_docs       = resp["unmatched_slips"] + [m["slip"] for m in resp["matches"]]
    matches         = [MatchView(...) for m in resp["matches"]]
    verified_months = { mv.credit.month for mv in matches if mv.credit.month }
    mark stage "completed"
except (UpstreamUnreachableError, UpstreamHttpError) as exc:
    audit.warnings.append(f"ocr_match unreachable; slips via ocr_slip fallback: {exc}")
    slip_docs       = await upstream.parse_slips(slip_pdfs, password=password)  # fallback
    matches         = []
    verified_months = set()
    mark stage "completed"   # degraded, not failed
```

- `MatchView.credit.month` falls back to `credit.tanggal[:7]` when the response's
  `month` field is absent.
- If the `ocr_slip` fallback **also** fails, catch it too: `slip_docs = []`, append
  a second warning, still complete the stage. Income then computes from bank
  credits alone (or yields `basis="none"` if there are none).
- The single orchestrator `password` is forwarded as both `slip_password` and
  `mutation_password` to `ocr_match` (its endpoint takes them separately).

### 4.2 Re-ordering: slip → `doc_results` attachment

Today the extract stage attaches per-slip extraction onto `doc_results`
(`d.extracted = slip_by_file.get(d.filename)`). Since slip data now arrives in the
**match** stage, this attachment moves to **after** stage 3. The keying is
unchanged: `slip_by_file` is built with the existing `_slip_base(source_file)`
helper, which still works because `ocr_match`'s `ParsedSlip.source_file` is
`ocr_slip`'s same rewritten value. Mutasi/sk attachment stays in the extract stage.

---

## 5. Components changed

| File | Change |
|---|---|
| `ocr_orchestrator/upstream.py` | **Add** `match_documents(slip_pdfs, mutasi_pdfs, *, password)` → `POST {ocr_match_url}/api/v1/match` (multipart `slips`, `mutations`, `slip_password`, `mutation_password`), returns parsed JSON dict; raises the existing `UpstreamUnreachableError` / `UpstreamHttpError`. **Keep** `parse_slips` (now fallback-only). |
| `ocr_orchestrator/verify.py` | Rewritten as the **match adapter**: `MatchResponse` JSON → `(slip_docs: list[dict], matches: list[MatchView], verified_months: set[str])`. **No `ocr_match` imports.** (File may be renamed `match.py`; keep `verify.py` if it reduces churn — implementer's call, noted in plan.) |
| `ocr_orchestrator/models.py` | **Add** local `MatchView` with nested `slip.source_file` and `credit` (`month`, `tanggal`, `amount`) plus `match_pattern`. Plain Pydantic; only the fields `monthly.py` and `_match_pair_view` read. |
| `ocr_orchestrator/slip_dates.py` | **New.** Local `_slip_month` / `_credit_month` (pure date derivation copied out of `ocr_match.pipeline` — slip `period` → filename month/year regex → `YYYY-MM`; credit `tanggal[:7]`). This is slip *placement*, not matching, so goal B is preserved. |
| `ocr_orchestrator/monthly.py` | Drop `from ocr_match...` imports; use local `slip_dates._slip_month` and iterate `MatchView`. `slip_docs` stay plain dicts (same keys `ocr_slip` emits). |
| `ocr_orchestrator/pipeline.py` | Rename verify→match stage; remove `ocr_slip` from extract; wire match stage + `ocr_slip` fallback; move slip `doc_results` attachment after match. |
| `ocr_orchestrator/config.py` | **Add** `ocr_match_url: str = "http://127.0.0.1:5005"` and `match_timeout_s: float` (generous — this call runs full OCR+LLM; default to `upstream_timeout_s`). **Keep** `ocr_slip_url` (fallback). **Update docstring:** orchestrator no longer imports `ocr_match`, so remove the note about `ocr_match.config` requiring `AZURE_OPENAI_*` keys. |
| `.env.example` | `OCR_MATCH_URL` already present; confirm and document that the orchestrator now consumes it. |

`compute_income`, `build_monthly_breakdown` signatures, `decision.py`, `identity.py`,
`income.py`, `fmv`/`decide` stages: **unchanged**.

---

## 6. Error handling

- `match_documents` mirrors the existing upstream clients: `httpx.TransportError`
  → `UpstreamUnreachableError`; `>=400` → `UpstreamHttpError`.
- Match-stage outage path is §4.1: warn + `ocr_slip` fallback + complete (degraded).
- The match stage never fails the job (only the classifier stage fails jobs, per
  the existing design). The `run_job` backstop still converts any unexpected
  exception into a failed job.

---

## 7. Parsing cost (explicit)

- **Slips: parsed once** — inside `ocr_match` (happy path) or `ocr_slip` (fallback),
  never both.
- **Mutasi: parsed twice** — the orchestrator's own `ocr_mutasi` all-category call
  **plus** `ocr_match`'s internal `Gaji`-only pass. Unavoidable under §2; accepted.
- *Optional future optimization (not in this spec):* the match call and the
  orchestrator's mutasi extract both need only raw PDFs, so they could run
  concurrently to hide the second mutasi parse. Kept sequential here to preserve
  the clean per-stage `job.stages` tracking.

---

## 8. Testing

- `tests/test_upstream.py` — `match_documents`: success, `UpstreamUnreachableError`,
  `UpstreamHttpError` (httpx mocked, same pattern as existing upstream tests).
  `parse_slips` fallback path remains covered.
- `tests/test_verify.py` (match adapter) — sample `MatchResponse` JSON →
  asserts `slip_docs` (union of matched + unmatched), `MatchView` list, and
  `verified_months`; `month` fallback to `tanggal[:7]`.
- `tests/test_pipeline.py` — patch `upstream.match_documents`:
  - happy path: slips come from `ocr_match`; `ocr_slip` **not** called; income +
    breakdown correct.
  - degrade path: `match_documents` raises → `upstream.parse_slips` fallback is
    called; job `completed`; income `bank_unverified`; warning present.
  - both-fail path: `match_documents` and `parse_slips` raise → `slip_docs` empty;
    job still `completed`.
- `tests/test_monthly.py` — construct `MatchView`s (not `ocr_match.MatchPair`);
  assert breakdown rows unchanged for equivalent inputs.
- `tests/test_slip_dates.py` (new) — `_slip_month` (period > filename regex >
  `YYYY-MM`) and `_credit_month`.
- **Decoupling guard:** a test (or CI grep) asserting **zero `import ocr_match`**
  anywhere under `ocr_orchestrator/` (including `tests/`).

---

## 9. Out of scope

- Any change to `ocr_match` (e.g. adding a parsed-input endpoint) — explicitly
  forbidden by §2.
- The income formula, `fmv`, `decide`, `identity`, and frontend wiring.
- Eliminating the mutasi double-parse (would require touching `ocr_match`).
- Concurrency optimization of match vs extract (§7).
