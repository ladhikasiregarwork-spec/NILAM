"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { FlowStep, PersonaConfig, SurveyStatus } from "@/types/flow";
import { SURVEY_THRESHOLD } from "@/types/flow";
import type { OrchestrationEvent, NodeId } from "@/types/orchestration";
import type { CustomerIncome, ComponentKey, ComponentMode } from "@/types/income";
import type { OcrResults, ClassifyResult, PreviewDoc } from "@/types/ocrExtract";
import type { DocumentId } from "@/types/documents";
import type { AgunanData } from "@/types/agunan";
import type { SlikReport } from "@/types/profile";
import type { UserInput } from "@/types/userInput";
import { usiaDariKtp } from "@/lib/usia";
import { type AgunanKlasifikasi, DEFAULT_KLASIFIKASI } from "@/data/ltv";
import type { EventListener } from "@/engines/orchestrator/events";
import { planFlow } from "@/engines/persona/personaEngine";
import { WorkflowOrchestrator } from "@/engines/orchestrator/workflowOrchestrator";
import { DEFAULT_PERSONA } from "@/data/personas";
import { SLIP_GAJI, MUTASI, IDENTITY_PASANGAN } from "@/data/ocrFixtures";
import { SLIK_NASABAH, SLIK_PASANGAN } from "@/data/slikFixtures";
import { FRAUD_RESULT } from "@/data/fraudFixtures";
import { NASABAH_INCOME, PASANGAN_INCOME } from "@/data/incomeFixtures";
import type { ApplicationView, ProcessResponse } from "@/types/applicationView";
import {
  buildProcessRequest,
  fetchApplicationView,
  legToCustomerIncome,
  mapBackendEvent,
  processApplication,
  submitSurveyDecision,
} from "@/lib/nilamBackend";

// Small per-node delay so the server's (synchronous) events still animate the
// Processing screen timeline instead of snapping to done.
const REPLAY_DELAY_MS = 120;
const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function makeAppId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `app-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface NilamState {
  persona: PersonaConfig;
  steps: FlowStep[];
  stepIndex: number;
  jointAnswer: "ya" | "tidak" | null;
  uploads: Record<string, boolean>;
  events: OrchestrationEvent[];
  nasabah?: CustomerIncome;
  pasangan?: CustomerIncome;
  /** Real OCR-extracted data for Slip Gaji & SK Perusahaan (when uploaded). */
  ocr: OcrResults;
  /** Number of files classified per document type (e.g. how many slip/mutasi). */
  docCounts: Partial<Record<DocumentId, number>>;
  /** Collateral/property data (manual or from a Rumah123 link). */
  agunan?: AgunanData;
  /** SLIK report fetched by NIK (from the SLIK CSV). */
  slik?: SlikReport;
  /** NPW (Nilai Pasar Wajar) from the appraisal model, by agunan. */
  npw?: number;
  /** Land value portion of the NPW (for the nearby land-price comparison). */
  npwLand?: number;
  /** Collateral classification (drives LTV), shared by the dashboard + offer. */
  agunanKlas: AgunanKlasifikasi;
  /** Borrower application data (prefilled from OCR, editable on Data Diri). */
  userInput: UserInput;
  /** Uploaded documents kept for preview (blob URLs + classified type). */
  previewDocs: PreviewDoc[];
  /** RM survey status (for collateral ≥ SURVEY_THRESHOLD). */
  surveyStatus: SurveyStatus;
  /** Appraised value entered by the RM during the survey (overrides NPW once approved). */
  surveyValue?: number;
  /** RM survey note. */
  surveyNote?: string;
  /** Application id for the current backend pipeline run (set on submit). */
  appId?: string;
  /** Authoritative ApplicationView assembled by nilam_backend (the server decides). */
  view?: ApplicationView;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export type NilamAction =
  | { type: "setNasabahPayroll"; value: boolean }
  | { type: "setPasanganPayroll"; value: boolean }
  | { type: "next" }
  | { type: "goTo"; step: FlowStep }
  | { type: "goBack" }
  | { type: "setJointAnswer"; answer: "ya" | "tidak" }
  | { type: "setUpload"; key: string; value?: boolean }
  | { type: "appendEvent"; event: OrchestrationEvent }
  | { type: "setIncome"; role: "nasabah" | "pasangan"; income: CustomerIncome }
  | { type: "setComponent"; role: "nasabah" | "pasangan"; key: ComponentKey; patch: { mode?: ComponentMode; weight?: number } }
  | { type: "setOcr"; doc: keyof OcrResults; data: OcrResults[keyof OcrResults] }
  | { type: "classify"; counts: Partial<Record<DocumentId, number>> }
  | { type: "clearUploads" }
  | { type: "setAgunan"; data: AgunanData }
  | { type: "clearAgunan" }
  | { type: "setSlik"; data: SlikReport }
  | { type: "setNpw"; value: number | undefined; land?: number }
  | { type: "setAgunanKlas"; patch: Partial<AgunanKlasifikasi> }
  | { type: "setUserInput"; patch: Partial<UserInput> }
  | { type: "prefillUserInput"; data: Partial<UserInput> }
  | { type: "addPreviewDocs"; docs: PreviewDoc[] }
  | { type: "setSurveyStatus"; status: SurveyStatus }
  | { type: "submitSurvey"; decision: "approved" | "rejected"; value?: number; note?: string }
  | { type: "startRun"; appId: string }
  | { type: "setView"; view: ApplicationView }
  | { type: "reset" };

// ---------------------------------------------------------------------------
// Initial state factory
// ---------------------------------------------------------------------------

export function initialState(): NilamState {
  return {
    persona: DEFAULT_PERSONA,
    steps: planFlow(DEFAULT_PERSONA),
    stepIndex: 0,
    jointAnswer: null,
    uploads: {},
    events: [],
    nasabah: undefined,
    pasangan: undefined,
    ocr: {},
    docCounts: {},
    userInput: {},
    previewDocs: [],
    agunanKlas: DEFAULT_KLASIFIKASI,
    surveyStatus: "none",
  };
}

// ---------------------------------------------------------------------------
// Helper: reset flow fields but keep persona patch applied
// ---------------------------------------------------------------------------

function resetWithPersona(persona: PersonaConfig): NilamState {
  return {
    persona,
    steps: planFlow(persona),
    stepIndex: 0,
    jointAnswer: null,
    uploads: {},
    events: [],
    nasabah: undefined,
    pasangan: undefined,
    ocr: {},
    docCounts: {},
    userInput: {},
    previewDocs: [],
    agunanKlas: DEFAULT_KLASIFIKASI,
    surveyStatus: "none",
  };
}

// ---------------------------------------------------------------------------
// Pure reducer — exported so it can be unit-tested in isolation
// ---------------------------------------------------------------------------

export function nilamReducer(state: NilamState, action: NilamAction): NilamState {
  switch (action.type) {
    case "setNasabahPayroll": {
      const persona: PersonaConfig = { ...state.persona, nasabahPayroll: action.value };
      return resetWithPersona(persona);
    }

    case "setPasanganPayroll": {
      const persona: PersonaConfig = { ...state.persona, pasanganPayroll: action.value };
      return resetWithPersona(persona);
    }

    case "next":
      return {
        ...state,
        stepIndex: Math.min(state.stepIndex + 1, state.steps.length - 1),
      };

    case "goTo": {
      const idx = state.steps.indexOf(action.step);
      if (idx === -1) return state;
      return { ...state, stepIndex: idx };
    }

    case "goBack": {
      const leavingStep = state.steps[state.stepIndex];
      const nextIndex = Math.max(state.stepIndex - 1, 0);
      const isRollingBack = leavingStep === "processing" || leavingStep === "analyst_decision";
      return {
        ...state,
        stepIndex: nextIndex,
        // Rollback pipeline state when leaving processing or analyst_decision
        ...(isRollingBack
          ? { events: [], nasabah: undefined, pasangan: undefined, view: undefined }
          : {}),
      };
    }

    case "setJointAnswer":
      return { ...state, jointAnswer: action.answer };

    case "setUpload":
      return {
        ...state,
        uploads: { ...state.uploads, [action.key]: action.value ?? true },
      };

    case "appendEvent":
      return { ...state, events: [...state.events, action.event] };

    case "setIncome":
      return {
        ...state,
        [action.role === "nasabah" ? "nasabah" : "pasangan"]: action.income,
      };

    case "setComponent": {
      const field = action.role === "nasabah" ? "nasabah" : "pasangan";
      const customer = state[field];
      if (!customer) return state;
      return {
        ...state,
        [field]: {
          ...customer,
          components: customer.components.map((c) =>
            c.key === action.key ? { ...c, ...action.patch } : c
          ),
        },
      };
    }

    case "setOcr":
      return { ...state, ocr: { ...state.ocr, [action.doc]: action.data } };

    case "classify": {
      const uploads = { ...state.uploads };
      const docCounts = { ...state.docCounts };
      for (const [key, count] of Object.entries(action.counts)) {
        if (!count) continue;
        uploads[key] = true;
        docCounts[key as DocumentId] = (docCounts[key as DocumentId] ?? 0) + count;
      }
      return { ...state, uploads, docCounts };
    }

    case "clearUploads":
      return { ...state, uploads: {}, docCounts: {}, ocr: {}, previewDocs: [] };

    case "addPreviewDocs":
      return { ...state, previewDocs: [...state.previewDocs, ...action.docs] };

    case "setSurveyStatus":
      return { ...state, surveyStatus: action.status };

    case "submitSurvey": {
      // RM finished the on-site survey. On approval the borrower advances from
      // the waiting screen to the offer (using the RM's appraised value); on
      // rejection they stay on the survey step and see the rejection notice.
      if (action.decision === "approved") {
        const idx = state.steps.indexOf("offering");
        return {
          ...state,
          surveyStatus: "approved",
          surveyValue: action.value,
          surveyNote: action.note,
          stepIndex: idx === -1 ? state.stepIndex : idx,
        };
      }
      return {
        ...state,
        surveyStatus: "rejected",
        surveyValue: action.value,
        surveyNote: action.note,
      };
    }

    case "setAgunan":
      return { ...state, agunan: { ...state.agunan, ...action.data } };

    case "clearAgunan":
      return { ...state, agunan: undefined, npw: undefined, npwLand: undefined };

    case "setNpw":
      return { ...state, npw: action.value, npwLand: action.land };

    case "setAgunanKlas":
      return { ...state, agunanKlas: { ...state.agunanKlas, ...action.patch } };

    case "setSlik":
      return { ...state, slik: action.data };

    case "setUserInput":
      return { ...state, userInput: { ...state.userInput, ...action.patch } };

    case "prefillUserInput":
      // OCR-derived defaults fill only fields the user hasn't set yet.
      return { ...state, userInput: { ...action.data, ...state.userInput } };

    case "startRun":
      // Fresh pipeline run: new application id, clear prior events/income/view.
      return {
        ...state,
        appId: action.appId,
        events: [],
        nasabah: undefined,
        pasangan: undefined,
        view: undefined,
      };

    case "setView":
      return { ...state, view: action.view };

    case "reset":
      return initialState();

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNilamFlow() {
  const [state, dispatch] = useReducer(nilamReducer, undefined, initialState);

  // Always-fresh mirror of state so callbacks (submit) never read a stale
  // closure — critical for the ≥ threshold survey decision after async work.
  const stateRef = useRef(state);
  stateRef.current = state;

  // Holds the active orchestrator so we can cancel it on navigation or reset.
  const orchestratorRef = useRef<WorkflowOrchestrator | null>(null);

  // Monotonic token identifying the current pipeline run. Bumped on every
  // cancel so an in-flight async backend run (awaiting fetch / replaying events)
  // can detect it was superseded and stop dispatching.
  const runIdRef = useRef(0);

  // Cancel the current orchestrator and clear the ref so the `.then` guard
  // in submit() knows the run was abandoned; also invalidate any backend run.
  const cancelOrchestrator = useCallback(() => {
    orchestratorRef.current?.cancel();
    orchestratorRef.current = null;
    runIdRef.current += 1;
  }, []);

  // Cancel on unmount to prevent dispatching to a stale component.
  useEffect(() => {
    return () => {
      cancelOrchestrator();
    };
  }, [cancelOrchestrator]);

  // Derived state
  const currentStep = state.steps[state.stepIndex];
  const isJoint = state.jointAnswer === "ya";
  const canGoBack =
    state.stepIndex > 0 &&
    currentStep !== "processing" &&
    currentStep !== "survey" &&
    currentStep !== "analyst_decision";

  // -------------------------------------------------------------------------
  // Public actions
  // -------------------------------------------------------------------------

  const setNasabahPayroll = useCallback(
    (v: boolean) => {
      cancelOrchestrator();
      dispatch({ type: "setNasabahPayroll", value: v });
    },
    [cancelOrchestrator]
  );

  const setPasanganPayroll = useCallback(
    (v: boolean) => {
      cancelOrchestrator();
      dispatch({ type: "setPasanganPayroll", value: v });
    },
    [cancelOrchestrator]
  );

  const start = useCallback(() => {
    dispatch({ type: "next" });
  }, []);

  const next = useCallback(() => {
    dispatch({ type: "next" });
  }, []);

  const goBack = useCallback(() => {
    cancelOrchestrator();
    dispatch({ type: "goBack" });
  }, [cancelOrchestrator]);

  // Jump straight back to the Agunan step (e.g. from the offer or a rejected
  // survey) to swap the collateral. Withdraw from the RM survey queue first so a
  // stale pending entry can't be approved mid-edit; re-submit re-runs everything.
  const editAgunan = useCallback(() => {
    cancelOrchestrator();
    dispatch({ type: "setSurveyStatus", status: "none" });
    dispatch({ type: "goTo", step: "agunan" });
  }, [cancelOrchestrator]);

  const setJointAnswer = useCallback((ans: "ya" | "tidak") => {
    dispatch({ type: "setJointAnswer", answer: ans });
  }, []);

  const setUpload = useCallback((key: string, value = true) => {
    dispatch({ type: "setUpload", key, value });
  }, []);

  // Real upload: send a PDF to the Next.js OCR proxy, store the extracted data,
  // and mark the document uploaded. Used for Slip Gaji & SK Perusahaan.
  const uploadOcrDocument = useCallback(
    async (
      docId: "slip_gaji" | "sk_perusahaan",
      files: File[],
    ): Promise<{ ok: boolean; error?: string }> => {
      if (!files.length) return { ok: false, error: "Tidak ada file dipilih" };
      const endpoint = docId === "slip_gaji" ? "/api/ocr/slip-gaji" : "/api/ocr/sk-perusahaan";
      const form = new FormData();
      for (const f of files) form.append("file", f);
      try {
        const resp = await fetch(endpoint, { method: "POST", body: form });
        const json = await resp.json().catch(() => null);
        if (!resp.ok || !json?.ok) {
          return { ok: false, error: json?.error ?? `Gagal memproses dokumen (${resp.status})` };
        }
        dispatch({
          type: "setOcr",
          doc: docId === "slip_gaji" ? "slipGaji" : "skPerusahaan",
          data: json.extract,
        });
        dispatch({ type: "setUpload", key: docId, value: true });
        return { ok: true };
      } catch {
        return { ok: false, error: "Tidak dapat menghubungi server OCR" };
      }
    },
    [],
  );

  // Single upload menu: classify every file (local classifier), assign each to a
  // document type, count them, then run OCR extraction for slip & SK.
  const classifyAndUpload = useCallback(
    async (
      files: File[],
    ): Promise<{ ok: boolean; results?: ClassifyResult[]; error?: string }> => {
      if (!files.length) return { ok: false, error: "Tidak ada file dipilih" };

      let results: ClassifyResult[];
      try {
        const form = new FormData();
        for (const f of files) form.append("file", f);
        const resp = await fetch("/api/ocr/classify", { method: "POST", body: form });
        const json = await resp.json().catch(() => null);
        if (!resp.ok || !json?.ok) {
          return { ok: false, error: json?.error ?? `Gagal mengklasifikasi (${resp.status})` };
        }
        results = json.results as ClassifyResult[];
      } catch {
        return { ok: false, error: "Tidak dapat menghubungi server classifier" };
      }

      // Group files by detected document type. One upload menu handles ALL docs
      // (KTP/KK included) — each is auto-classified, then OCR-extracted below.
      const LABEL_TO_DOC: Record<string, DocumentId | undefined> = {
        ktp: "ktp",
        kk: "kk",
        slip: "slip_gaji",
        mutasi: "mutasi",
        sk: "sk_perusahaan",
        unknown: undefined,
      };
      const groups: Partial<Record<DocumentId, File[]>> = {};
      results.forEach((r, i) => {
        const docId = LABEL_TO_DOC[r.type];
        if (!docId || !files[i]) return;
        (groups[docId] ??= []).push(files[i]);
      });

      // Keep each uploaded file (blob URL + classified type) for the dashboard
      // document preview.
      const previewDocs: PreviewDoc[] = [];
      results.forEach((r, i) => {
        if (files[i]) previewDocs.push({ type: r.type, url: URL.createObjectURL(files[i]), originalName: files[i].name });
      });
      if (previewDocs.length) dispatch({ type: "addPreviewDocs", docs: previewDocs });

      const counts: Partial<Record<DocumentId, number>> = {};
      (Object.keys(groups) as DocumentId[]).forEach((k) => {
        counts[k] = groups[k]!.length;
      });
      dispatch({ type: "classify", counts });

      // Extract content for the dashboard cards.
      if (groups.ktp?.length) {
        // The classifier already extracted KTP fields in the same OCR pass —
        // reuse them instead of OCR-ing the KTP a second time.
        const ktpExtract = results.find((r) => r.type === "ktp" && r.extract)?.extract;
        if (ktpExtract) dispatch({ type: "setOcr", doc: "ktp", data: ktpExtract });
        else await uploadIdentitas("ktp", groups.ktp);
        // Pull the SLIK report for this NIK (from the SLIK CSV).
        const nik = ktpExtract?.nik;
        if (nik) {
          try {
            const r = await fetch(`/api/slik?nik=${encodeURIComponent(nik)}`);
            const j = await r.json().catch(() => null);
            if (r.ok && j?.ok && j.report) dispatch({ type: "setSlik", data: j.report });
          } catch {
            /* SLIK is best-effort */
          }
        }
      }
      if (groups.kk?.length) await uploadIdentitas("kk", groups.kk);
      if (groups.slip_gaji?.length) {
        const f = new FormData();
        for (const file of groups.slip_gaji) f.append("file", file); // all slips (per payment date)
        try {
          const resp = await fetch("/api/ocr/slip", { method: "POST", body: f });
          const json = await resp.json().catch(() => null);
          if (resp.ok && json?.ok) dispatch({ type: "setOcr", doc: "slipGaji", data: json.extract });
        } catch {
          /* best-effort */
        }
      }
      if (groups.sk_perusahaan?.length) {
        const f = new FormData();
        f.append("file", groups.sk_perusahaan[0]);
        try {
          const resp = await fetch("/api/ocr/sk", { method: "POST", body: f });
          const json = await resp.json().catch(() => null);
          if (resp.ok && json?.ok) dispatch({ type: "setOcr", doc: "skPerusahaan", data: json.extract });
        } catch {
          /* best-effort */
        }
      }
      if (groups.mutasi?.length) {
        const f = new FormData();
        for (const file of groups.mutasi) f.append("file", file); // all months
        try {
          const resp = await fetch("/api/ocr/mutasi", { method: "POST", body: f });
          const json = await resp.json().catch(() => null);
          if (resp.ok && json?.ok) dispatch({ type: "setOcr", doc: "mutasi", data: json.extract });
        } catch {
          /* mutasi extraction is best-effort */
        }
      }

      return { ok: true, results };
    },
    [uploadOcrDocument],
  );

  const clearUploads = useCallback(() => {
    dispatch({ type: "clearUploads" });
  }, []);

  // Separate KTP/KK upload: read the document via OCR (Tesseract + regex) and
  // store the extracted identity — not dummy/auto-input.
  const uploadIdentitas = useCallback(
    async (docId: "ktp" | "kk", files: File[]): Promise<{ ok: boolean; error?: string }> => {
      if (!files.length) return { ok: false, error: "Tidak ada file dipilih" };
      const form = new FormData();
      form.append("file", files[0]);
      form.append("type", docId);
      try {
        const resp = await fetch("/api/ocr/identitas", { method: "POST", body: form });
        const json = await resp.json().catch(() => null);
        if (!resp.ok || !json?.ok) {
          return { ok: false, error: json?.error ?? `Gagal membaca dokumen (${resp.status})` };
        }
        dispatch({ type: "setOcr", doc: docId, data: json.extract });
        dispatch({ type: "setUpload", key: docId, value: true });
        return { ok: true };
      } catch {
        return { ok: false, error: "Tidak dapat menghubungi server OCR" };
      }
    },
    [],
  );

  const setAgunan = useCallback((data: AgunanData) => {
    dispatch({ type: "setAgunan", data });
  }, []);

  const clearAgunan = useCallback(() => {
    dispatch({ type: "clearAgunan" });
  }, []);

  const setUserInput = useCallback((patch: Partial<UserInput>) => {
    dispatch({ type: "setUserInput", patch });
  }, []);

  const setAgunanKlas = useCallback((patch: Partial<AgunanKlasifikasi>) => {
    dispatch({ type: "setAgunanKlas", patch });
  }, []);

  // Pull the SLIK report (Excel by NIK) as soon as the KTP NIK is known.
  useEffect(() => {
    const nik = state.ocr.ktp?.nik;
    if (!nik || state.slik) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/slik?nik=${encodeURIComponent(nik)}`);
        const j = await r.json().catch(() => null);
        if (!cancelled && r.ok && j?.ok && j.report) dispatch({ type: "setSlik", data: j.report });
      } catch {
        /* best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.ocr.ktp?.nik, state.slik]);

  // Appraise NPW (Nilai Pasar Wajar) from the agunan whenever its size/location
  // changes (via the house_fair_market_value model).
  useEffect(() => {
    const a = state.agunan;
    if (!a?.luasTanah || a.luasTanah <= 0) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/npw", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            luasTanah: a.luasTanah,
            luasBangunan: a.luasBangunan,
            kodepos: a.kodepos,
            kelurahan: a.kelurahan,
          }),
        });
        const j = await r.json().catch(() => null);
        if (!cancelled && r.ok && j?.ok && j.fairValue != null) {
          dispatch({
            type: "setNpw",
            value: Math.round(j.fairValue),
            land: j.landValue != null ? Math.round(j.landValue) : undefined,
          });
        }
      } catch {
        /* best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.agunan?.luasTanah, state.agunan?.luasBangunan, state.agunan?.kelurahan, state.agunan?.kodepos]);

  // Prefill the Data Diri form from KTP/KK OCR (only fields not yet edited).
  useEffect(() => {
    const ktp = state.ocr.ktp;
    const kk = state.ocr.kk;
    const prefill: Partial<UserInput> = {};
    if (ktp?.nik) prefill.nik = ktp.nik;
    if (ktp?.nama) prefill.nama = ktp.nama;
    const usia = usiaDariKtp(ktp?.tanggalLahir);
    if (usia != null) prefill.usia = usia;
    if (ktp?.statusPerkawinan) prefill.statusKawin = ktp.statusPerkawinan;
    if (kk?.members?.length) prefill.jumlahTanggungan = Math.max(0, kk.members.length - 1);
    if (Object.keys(prefill).length) dispatch({ type: "prefillUserInput", data: prefill });
  }, [state.ocr.ktp, state.ocr.kk]);

  // Fetch & extract agunan data from a property listing link (Rumah123).
  const fetchAgunanFromLink = useCallback(
    async (url: string): Promise<{ ok: boolean; error?: string }> => {
      try {
        const resp = await fetch("/api/agunan/from-link", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        const json = await resp.json().catch(() => null);
        if (!resp.ok || !json?.ok) {
          return { ok: false, error: json?.error ?? `Gagal mengambil data (${resp.status})` };
        }
        dispatch({ type: "setAgunan", data: json.data });
        return { ok: true };
      } catch {
        return { ok: false, error: "Tidak dapat menghubungi server" };
      }
    },
    [],
  );

  const setComponentMode = useCallback(
    (role: "nasabah" | "pasangan", key: ComponentKey, mode: ComponentMode) => {
      dispatch({ type: "setComponent", role, key, patch: { mode } });
    },
    []
  );

  const setComponentWeight = useCallback(
    (role: "nasabah" | "pasangan", key: ComponentKey, weight: number) => {
      dispatch({ type: "setComponent", role, key, patch: { weight } });
    },
    []
  );

  const reset = useCallback(() => {
    cancelOrchestrator();
    dispatch({ type: "reset" });
  }, [cancelOrchestrator]);

  // -------------------------------------------------------------------------
  // submit() — orchestration kick (called from Requirement step)
  // -------------------------------------------------------------------------

  // RM submits the survey result for the current (≥ threshold) application. The
  // backend overrides NPW with the appraised value and recomputes the offer; we
  // refresh the stored view, then apply the local navigation.
  const submitSurvey = useCallback(
    async (decision: "approved" | "rejected", value?: number, note?: string) => {
      const appId = stateRef.current.appId;
      if (appId) {
        const result = await submitSurveyDecision(appId, decision, value, note);
        if (result && decision === "approved") {
          const refreshed = await fetchApplicationView(appId);
          if (refreshed) dispatch({ type: "setView", view: refreshed });
        }
      }
      dispatch({ type: "submitSurvey", decision, value, note });
    },
    [],
  );

  // Fallback: the original in-browser fixture pipeline. Used when the backend is
  // unreachable so the demo still runs end-to-end without the Python services.
  const runFixturePipeline = useCallback(
    (s: NilamState, runId: number, joint: boolean, needsSurvey: boolean) => {
      const outputs: Partial<Record<NodeId, unknown>> = {
        upload:   { files: ["slip_gaji_nasabah.pdf", "mutasi_12_bulan.pdf"] },
        ocr:      { slip: SLIP_GAJI, mutasi: MUTASI },
        validasi: { monthsVerified: 12, complete: true },
        fraud:    FRAUD_RESULT,
        identity: joint ? IDENTITY_PASANGAN : null,
        slik:     { nasabah: SLIK_NASABAH, pasangan: joint ? SLIK_PASANGAN : undefined },
        income:   { nasabah: NASABAH_INCOME, pasangan: joint ? PASANGAN_INCOME : undefined },
        thp:      null,
      };

      const orch = new WorkflowOrchestrator();
      orchestratorRef.current = orch;

      const emit: EventListener = (e) => {
        dispatch({ type: "appendEvent", event: e });
        if (e.status === "success" && e.nodeId === "income" && e.output) {
          const out = e.output as { nasabah: CustomerIncome; pasangan?: CustomerIncome };
          dispatch({ type: "setIncome", role: "nasabah", income: out.nasabah });
          if (out.pasangan) dispatch({ type: "setIncome", role: "pasangan", income: out.pasangan });
        }
      };

      orch.run(s.persona, outputs, emit).then(() => {
        if (orchestratorRef.current !== orch || runIdRef.current !== runId) return;
        if (needsSurvey) {
          dispatch({ type: "setSurveyStatus", status: "pending" });
          dispatch({ type: "goTo", step: "survey" });
        } else {
          dispatch({ type: "goTo", step: "offering" });
        }
      });
    },
    [],
  );

  const submit = useCallback(() => {
    // Cancel any in-flight run (bumps runIdRef) before starting a new one.
    cancelOrchestrator();
    const runId = runIdRef.current;

    // Fresh survey state for this run (a re-submit after "Ganti Agunan").
    dispatch({ type: "setSurveyStatus", status: "none" });

    // Read the LATEST state from the ref (never a stale closure).
    const s = stateRef.current;
    const hargaAgunan = s.agunan?.harga ?? 0;
    const needsSurvey = hargaAgunan >= SURVEY_THRESHOLD;
    const joint = s.jointAnswer === "ya";

    // New application id + clear prior run state; show the processing screen.
    const appId = makeAppId();
    dispatch({ type: "startRun", appId });
    dispatch({ type: "goTo", step: "processing" });

    // Drive the authoritative backend pipeline. On any failure (services down,
    // bad response) fall back to the in-browser fixture pipeline.
    void (async () => {
      let res: ProcessResponse;
      try {
        const req = buildProcessRequest({
          joint,
          ocr: s.ocr,
          userInput: s.userInput,
          agunan: s.agunan,
          agunanKlas: s.agunanKlas,
          npw: s.npw,
          previewDocs: s.previewDocs,
        });
        res = await processApplication(appId, req);
      } catch {
        res = { ok: false as const };
      }
      if (runIdRef.current !== runId) return; // superseded/cancelled mid-flight

      if (!res.ok || !res.view) {
        runFixturePipeline(s, runId, joint, needsSurvey);
        return;
      }

      // Replay the server's events onto the timeline (animated).
      const events = (res.events ?? [])
        .map(mapBackendEvent)
        .filter((e): e is OrchestrationEvent => e !== null);
      for (const ev of events) {
        if (runIdRef.current !== runId) return;
        dispatch({ type: "appendEvent", event: ev });
        await delay(REPLAY_DELAY_MS);
      }
      if (runIdRef.current !== runId) return;

      // Adopt the server's authoritative results.
      const view = res.view;
      const angsuran = view.slik?.totalAngsuran ?? 0;
      if (view.income?.nasabah) {
        dispatch({
          type: "setIncome",
          role: "nasabah",
          income: legToCustomerIncome("nasabah", s.userInput.nama ?? "Nasabah", view.income.nasabah, angsuran),
        });
      }
      if (view.income?.pasangan) {
        dispatch({
          type: "setIncome",
          role: "pasangan",
          income: legToCustomerIncome("pasangan", "Pasangan", view.income.pasangan, 0),
        });
      }
      dispatch({ type: "setView", view });

      // Navigate on the server's survey decision (≥ threshold → RM queue).
      const surveyStatus = view.survey?.status ?? (needsSurvey ? "pending" : "none");
      if (surveyStatus === "pending") {
        dispatch({ type: "setSurveyStatus", status: "pending" });
        dispatch({ type: "goTo", step: "survey" });
      } else {
        dispatch({ type: "goTo", step: "offering" });
      }
    })();
  }, [cancelOrchestrator, runFixturePipeline]);

  return {
    persona: state.persona,
    jointAnswer: state.jointAnswer,
    isJoint,
    steps: state.steps,
    currentStep,
    stepIndex: state.stepIndex,
    canGoBack,
    uploads: state.uploads,
    events: state.events,
    nasabah: state.nasabah,
    pasangan: state.pasangan,
    ocr: state.ocr,
    docCounts: state.docCounts,
    agunan: state.agunan,
    slik: state.slik,
    npw: state.npw,
    npwLand: state.npwLand,
    agunanKlas: state.agunanKlas,
    setAgunanKlas,
    userInput: state.userInput,
    setUserInput,
    previewDocs: state.previewDocs,
    surveyStatus: state.surveyStatus,
    surveyValue: state.surveyValue,
    surveyNote: state.surveyNote,
    /** Authoritative ApplicationView from nilam_backend (undefined until a run completes / backend down). */
    view: state.view,
    appId: state.appId,
    submitSurvey,
    setNasabahPayroll,
    setPasanganPayroll,
    setJointAnswer,
    start,
    next,
    goBack,
    editAgunan,
    setUpload,
    uploadOcrDocument,
    classifyAndUpload,
    uploadIdentitas,
    clearUploads,
    setAgunan,
    clearAgunan,
    fetchAgunanFromLink,
    submit,
    setComponentMode,
    setComponentWeight,
    reset,
  };
}
