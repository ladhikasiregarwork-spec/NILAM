"""Orchestration pipeline (service 16). Drives the 8 UI nodes in order, emitting
running/success(/error) events, calling each calc/fixture service IN-PROCESS, and
assembling the ApplicationView. Node ids/labels/reasoning are ported from
`engines/orchestrator/{pipelines,workflowOrchestrator}.ts`; execution is real
(not delayed mock). A node that throws emits an `error` event and the pipeline
continues (design §7: degrade, not 500).

The service-wiring between nodes (income components -> capacity inputs, offering
-> representative installment -> credit score -> decision) is integration glue;
the per-service formulas it composes are the faithfully-ported engines.
"""

from datetime import datetime, timezone
from typing import List, Optional

from nilam_backend.app.settings import get_settings
from nilam_backend.core.jobs import Job
from nilam_backend.domain.documents import MutasiExtract, SlipGajiExtract
from nilam_backend.projection.application_view import assemble_application_view
from nilam_backend.projection.matching import build_match
from nilam_backend.services.capacity.logic import dir_rate, kemampuan_bayar, penghasilan_bulanan
from nilam_backend.services.coverage.logic import analyze_ocr_coverage
from nilam_backend.services.credit_score.logic import compute_credit_score
from nilam_backend.services.credit_score.models import CreditScoreInput
from nilam_backend.services.decision.logic import build_decision
from nilam_backend.services.fraud.logic import detect_fraud
from nilam_backend.services.identity.logic import get_identity
from nilam_backend.services.income.logic import build_income, extract_components
from nilam_backend.services.offering.logic import build_offering
from nilam_backend.services.plafond.logic import build_plafond
from nilam_backend.services.slik.logic import get_slik

NODES = [
    ("upload", "Upload"),
    ("ocr", "OCR"),
    ("validasi", "Validasi Dokumen"),
    ("fraud", "Fraud Detection"),
    ("identity", "Identity Check"),
    ("slik", "SLIK Retrieval"),
    ("income", "Income Extraction"),
    ("thp", "THP Engine"),
]

REASONING = {
    "upload": "Memuat dokumen yang diunggah ke pipeline pemrosesan…",
    "ocr": "Mengekstrak data dari Slip Gaji & Mutasi…",
    "validasi": "Memverifikasi kelengkapan mutasi >= 12 bulan & konsistensi periode…",
    "fraud": "Memeriksa keaslian & konsistensi dokumen…",
    "identity": "Verifikasi identitas pasangan via KTP…",
    "slik": "Menarik data biro kredit SLIK OJK…",
    "income": "Menstrukturkan komponen pendapatan…",
    "thp": "Menghitung THP & keputusan…",
}

# Default nasabah NIK when userInput has none (matches the identity/SLIK seed).
DEFAULT_NIK = "3201234567890002"


def _mutasi_iso_months(mutasi: MutasiExtract) -> List[str]:
    """Detected "YYYY-MM" months from credit/debit dates ("DD/MM/YY")."""
    out = set()
    for t in mutasi.transactions:
        parts = (t.tanggal or "").split("/")
        if len(parts) == 3:
            out.add("20{}-{}".format(parts[2][-2:], parts[1].zfill(2)))
    return sorted(out)


def _pick_offer(offering: dict):
    """Representative (angsuran, plafonFinal): the customer's tenor on the first
    eligible scheme (or that scheme's first option)."""
    tenor_target = offering.get("tenorNasabah")
    for scheme in offering.get("schemes", []):
        opts = scheme.get("tenorOptions", [])
        if not opts:
            continue
        chosen = next((o for o in opts if o.get("tenor") == tenor_target), opts[0])
        return chosen.get("angsuran", 0), chosen.get("plafonFinal", 0)
    return 0, 0


def compute_financials(ctx: dict, npw: float) -> dict:
    """plafond (11) -> offering (12) -> credit score (13) -> decision (19), for a
    given NPW. Reused by the survey re-offer when an RM value overrides NPW."""
    harga = ctx["harga"]
    uang_muka = ctx["uangMuka"]
    kemampuan = ctx["kemampuan"]
    penghasilan = ctx["penghasilan"]
    slik_angsuran = ctx["slikAngsuran"]
    usia = ctx["usia"]
    jangka = ctx["jangkaWaktu"]

    plafond = build_plafond(npw, harga, uang_muka, ctx["klas"])
    offering = build_offering(harga, uang_muka, usia, jangka, kemampuan, plafond["plafonAgunan"])
    angsuran_kpr, plafon_pembiayaan = _pick_offer(offering)

    score = compute_credit_score(CreditScoreInput(
        pendidikan=ctx["pendidikan"], statusKawin=ctx["statusKawin"], usia=usia,
        punyaSimpananBri=ctx["punyaSimpananBri"], jangkaWaktu=jangka,
        hargaRumah=harga, uangMuka=uang_muka, jumlahTanggungan=ctx["jumlahTanggungan"],
        incomeMonthly=penghasilan, angsuranBulanan=angsuran_kpr + slik_angsuran,
        plafond=plafon_pembiayaan or None,
    ))
    decision = build_decision(kemampuan, angsuran_kpr, score["score"], score["grade"])
    return {
        "plafond": plafond,
        "offering": offering,
        "creditScore": score,
        "decision": decision,
        "angsuranKpr": angsuran_kpr,
        "plafonPembiayaan": plafon_pembiayaan,
    }


def _assemble(job: Job, financials: dict, npw: Optional[float]) -> dict:
    c = job.context
    return assemble_application_view(
        app_id=job.id, uploads=c.get("uploads"), ocr=c.get("ocr"),
        coverage=c.get("coverage"), fraud=c.get("fraud"), identity=c.get("identity"),
        slik=c.get("slik"), income=c.get("income"), capacity=c.get("capacity"),
        matching=c.get("matching"), agunan=c.get("agunan"), npw=npw,
        financials=financials, survey=job.survey,
    )


def run_pipeline(job: Job, req) -> dict:
    settings = get_settings()
    job.status = "running"
    seq = {"n": 0}

    def emit(node_id, label, status, reasoning=None, output=None, detail=None):
        seq["n"] += 1
        ev = {"nodeId": node_id, "label": label, "status": status, "seq": seq["n"],
              "at": datetime.now(timezone.utc).isoformat()}
        if reasoning is not None:
            ev["reasoning"] = reasoning
        if output is not None:
            ev["output"] = output
        if detail is not None:
            ev["detail"] = detail
        job.add_event(ev)

    mutasi = req.ocr.mutasi
    slip_records = req.ocr.slipRecords
    joint = req.joint
    ui = req.userInput
    agunan = req.agunan
    npw = req.npw
    stage: dict = {}

    for node_id, label in NODES:
        emit(node_id, label, "running", reasoning=REASONING.get(node_id))
        try:
            if node_id == "upload":
                out = {"files": req.uploads}
            elif node_id == "ocr":
                m = build_match(mutasi, SlipGajiExtract(records=slip_records))
                stage["matching"] = {"monthlyRecap": m["recaps"], "incomeTransactions": m["txns"]}
                stage["ocr"] = {
                    "mutasi": mutasi.model_dump(),
                    "slipRecords": [r.model_dump() for r in slip_records],
                }
                out = {"mutasiTxns": len(mutasi.transactions), "slipRecords": len(slip_records)}
            elif node_id == "validasi":
                cov = analyze_ocr_coverage(_mutasi_iso_months(mutasi), min_months=12)
                stage["coverage"] = cov
                out = {"meetsMinimum": cov["meetsMinimum"], "isComplete": cov["isComplete"],
                       "rangeLabel": cov["rangeLabel"]}
            elif node_id == "fraud":
                stage["fraud"] = detect_fraud(stage.get("ocr"), mutasi.model_dump(), None)
                out = stage["fraud"]
            elif node_id == "identity":
                stage["identity"] = get_identity("ktp", "pasangan") if joint else None
                out = stage["identity"]
            elif node_id == "slik":
                rep = get_slik(ui.nik or DEFAULT_NIK)
                stage["slik"] = rep
                out = {"totalAngsuran": rep["totalAngsuran"], "kolekTerburuk": rep["kolekTerburuk"]}
            elif node_id == "income":
                slik_angsuran = (stage.get("slik") or {}).get("totalAngsuran", 0)
                pas_mutasi = req.pasanganOcr.mutasi if (joint and req.pasanganOcr) else None
                income = build_income(mutasi, slik_angsuran, joint, pas_mutasi, 0)
                stage["income"] = income
                comps = {c.key: c for c in extract_components(mutasi)}
                gaji, thr, bonus = comps["Gaji"].avg, comps["THR"].avg, comps["Bonus"].avg
                penghasilan = penghasilan_bulanan(gaji, thr, bonus)
                kemampuan = kemampuan_bayar(gaji, thr, bonus, slik_angsuran)
                stage["capacity"] = {"penghasilanBulanan": penghasilan,
                                     "dirRate": dir_rate(penghasilan), "kemampuanBayar": kemampuan}
                stage["ctx"] = {
                    "harga": agunan.harga, "uangMuka": ui.uangMuka, "klas": req.agunanKlas,
                    "kemampuan": kemampuan, "penghasilan": penghasilan, "slikAngsuran": slik_angsuran,
                    "usia": ui.usia, "jangkaWaktu": ui.jangkaWaktu, "pendidikan": ui.pendidikan,
                    "statusKawin": ui.statusKawin, "punyaSimpananBri": ui.punyaSimpananBri,
                    "jumlahTanggungan": ui.jumlahTanggungan,
                }
                out = {"thp": income["nasabah"]["thp"], "total": income["total"],
                       "kemampuanBayar": kemampuan}
            else:  # thp -> financial synthesis + decision
                fin = compute_financials(stage["ctx"], npw)
                stage["financials"] = fin
                out = {"decision": fin["decision"]["decision"], "angsuranKpr": fin["angsuranKpr"],
                       "plafonPembiayaan": fin["plafonPembiayaan"]}
            emit(node_id, label, "success", output=out)
        except Exception as e:  # noqa: BLE001 — degrade, not 500
            emit(node_id, label, "error", detail=str(e))

    # Survey gating: collateral >= threshold waits for an RM survey.
    if (agunan.harga or 0) >= settings.survey_threshold and job.survey.get("status", "none") == "none":
        job.survey = {"status": "pending"}

    job.context = {
        "ctx": stage.get("ctx"), "uploads": req.uploads, "ocr": stage.get("ocr"),
        "coverage": stage.get("coverage"), "fraud": stage.get("fraud"),
        "identity": stage.get("identity"), "slik": stage.get("slik"),
        "income": stage.get("income"), "capacity": stage.get("capacity"),
        "matching": stage.get("matching"), "agunan": agunan.model_dump(), "npw": npw,
    }
    job.result = _assemble(job, stage.get("financials") or {}, npw)
    job.status = "done"
    return job.result


def recompute_with_npw(job: Job, npw: float) -> Optional[dict]:
    """Re-run plafond/offering/score/decision with an RM-overridden NPW and refresh
    the stored ApplicationView. Returns the new view (or current if no context)."""
    ctx = (job.context or {}).get("ctx")
    if ctx is None:
        return job.result
    fin = compute_financials(ctx, npw)
    job.context["npw"] = npw
    job.result = _assemble(job, fin, npw)
    return job.result
