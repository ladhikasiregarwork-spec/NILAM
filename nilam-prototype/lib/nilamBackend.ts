/**
 * Client helpers for the authoritative `nilam_backend` pipeline, reached through
 * the Next.js BFF routes under `/api/applications/*`. Keeps the request-building
 * and event-mapping glue out of the flow hook.
 */

import type { AgunanKlasifikasi } from "@/data/ltv";
import type { AgunanData } from "@/types/agunan";
import type { CustomerIncome } from "@/types/income";
import type { OcrResults } from "@/types/ocrExtract";
import type { OrchestrationEvent, NodeId } from "@/types/orchestration";
import type { UserInput } from "@/types/userInput";
import type {
  ApplicationView,
  BackendEvent,
  ProcessRequest,
  ProcessResponse,
  ViewIncomeLeg,
  ViewSurvey,
} from "@/types/applicationView";

/** Fields of the flow state the backend pipeline needs. */
export interface ProcessInputs {
  joint: boolean;
  ocr: OcrResults;
  userInput: UserInput;
  agunan?: AgunanData;
  agunanKlas: AgunanKlasifikasi;
  npw?: number;
  previewDocs?: { originalName: string }[];
}

/** Assemble the ProcessRequest the backend consumes from current flow state. */
export function buildProcessRequest(s: ProcessInputs): ProcessRequest {
  const a = s.agunan;
  return {
    joint: s.joint,
    uploads: (s.previewDocs ?? []).map((d) => d.originalName),
    ocr: {
      mutasi: s.ocr.mutasi,
      slipRecords: s.ocr.slipGaji?.records ?? [],
    },
    // The real OCR flow captures one document set; spouse docs are not extracted
    // separately, so the joint leg is left to the backend's default (no pasangan
    // mutasi → nasabah-only total). Wired here for when spouse OCR is added.
    pasanganOcr: null,
    userInput: {
      nik: s.userInput.nik,
      nama: s.userInput.nama,
      pendidikan: s.userInput.pendidikan,
      statusKawin: s.userInput.statusKawin,
      usia: s.userInput.usia,
      jangkaWaktu: s.userInput.jangkaWaktu,
      uangMuka: s.userInput.uangMuka ?? 0,
      jumlahTanggungan: s.userInput.jumlahTanggungan,
    },
    agunan: {
      harga: a?.harga,
      luasTanah: a?.luasTanah,
      luasBangunan: a?.luasBangunan,
      kelurahan: a?.kelurahan,
      kodepos: a?.kodepos,
    },
    agunanKlas: s.agunanKlas,
    npw: s.npw ?? 0,
  };
}

const PIPELINE_NODES: NodeId[] = [
  "upload", "ocr", "validasi", "fraud", "identity", "slik", "income", "thp",
];

function isNodeId(id: string): id is NodeId {
  return (PIPELINE_NODES as string[]).includes(id);
}

/**
 * Map a backend event to the browser's OrchestrationEvent. The frontend feed
 * only knows idle|running|success, so a degraded `error` stage is surfaced as a
 * completed node whose reasoning carries the warning (design §7: degrade, not
 * fail). Events for unknown node ids are dropped.
 */
export function mapBackendEvent(e: BackendEvent): OrchestrationEvent | null {
  if (!isNodeId(e.nodeId)) return null;
  const ts = Date.parse(e.at);
  return {
    nodeId: e.nodeId,
    status: e.status === "error" ? "success" : e.status,
    label: e.label,
    reasoning: e.reasoning ?? (e.detail ? `⚠ ${e.detail}` : undefined),
    output: e.output,
    ts: Number.isNaN(ts) ? Date.now() : ts,
  };
}

/** Build a CustomerIncome (the flow's leg shape) from a backend income leg. */
export function legToCustomerIncome(
  role: "nasabah" | "pasangan",
  name: string,
  leg: ViewIncomeLeg,
  angsuran: number,
): CustomerIncome {
  return { role, name, components: leg.components, angsuran };
}

/** POST the bundle to the backend pipeline (via the BFF). */
export async function processApplication(
  appId: string,
  req: ProcessRequest,
  signal?: AbortSignal,
): Promise<ProcessResponse> {
  const resp = await fetch(`/api/applications/${encodeURIComponent(appId)}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  const json = (await resp.json().catch(() => null)) as ProcessResponse | null;
  if (!resp.ok || !json?.ok) {
    return { ok: false, error: json?.error ?? `Backend error (${resp.status})` };
  }
  return json;
}

/** Submit the RM survey decision; the backend overrides NPW and recomputes. */
export async function submitSurveyDecision(
  appId: string,
  decision: "approved" | "rejected",
  value?: number,
  note?: string,
): Promise<ViewSurvey | null> {
  try {
    const resp = await fetch(`/api/applications/${encodeURIComponent(appId)}/survey`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, value, note }),
    });
    const json = await resp.json().catch(() => null);
    if (resp.ok && json?.ok) {
      return { status: json.status, surveyValue: json.surveyValue, surveyNote: json.surveyNote };
    }
  } catch {
    /* backend survey is best-effort; local state still drives the UI */
  }
  return null;
}

/** Fetch the latest assembled ApplicationView (e.g. after a survey recompute). */
export async function fetchApplicationView(appId: string): Promise<ApplicationView | null> {
  try {
    const resp = await fetch(`/api/applications/${encodeURIComponent(appId)}`);
    const json = await resp.json().catch(() => null);
    if (resp.ok && json?.ok && json.view) return json.view as ApplicationView;
  } catch {
    /* best-effort */
  }
  return null;
}
