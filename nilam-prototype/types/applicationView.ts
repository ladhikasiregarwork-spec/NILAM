/**
 * Shapes exchanged with the authoritative `nilam_backend` (FastAPI, modular
 * monolith). The browser submits a ProcessRequest, the backend drives the
 * 8-node pipeline server-side and returns the assembled ApplicationView — the
 * single source of truth the dashboard reads. *Frontend may preview; the server
 * decides.* See `nilam_backend/services/orchestration/models.py` and
 * `nilam_backend/projection/application_view.py`.
 */

import type { AgunanKlasifikasi } from "@/data/ltv";
import type { MutasiExtract, SlipRecord } from "@/types/ocrExtract";
import type { IncomeComponent } from "@/types/income";
import type { SurveyStatus } from "@/types/flow";
import type { MatchTxn, MonthlyRecap } from "@/engines/matching/matchSlipMutasi";

/** OCR slice the backend consumes (already extracted by the per-doc proxy routes). */
export interface ProcessOcrInput {
  mutasi?: MutasiExtract;
  slipRecords?: SlipRecord[];
}

/** Borrower inputs forwarded to the backend (mirror of UserInputModel). */
export interface ProcessUserInput {
  nik?: string;
  nama?: string;
  pendidikan?: string;
  statusKawin?: string;
  usia?: number;
  jangkaWaktu?: number;
  uangMuka?: number;
  jumlahTanggungan?: number;
  punyaSimpananBri?: boolean;
}

/** Collateral inputs forwarded to the backend (mirror of AgunanModel). */
export interface ProcessAgunanInput {
  harga?: number;
  luasTanah?: number;
  luasBangunan?: number;
  kelurahan?: string;
  kodepos?: string;
}

/** Body of POST /api/applications/{id}/process. */
export interface ProcessRequest {
  joint: boolean;
  uploads: string[];
  ocr: ProcessOcrInput;
  pasanganOcr?: ProcessOcrInput | null;
  userInput: ProcessUserInput;
  agunan: ProcessAgunanInput;
  agunanKlas: AgunanKlasifikasi;
  /** NPW (fair value) precomputed by the npw service / from-link; 0 if unknown. */
  npw: number;
}

/** One lifecycle event as emitted by the backend pipeline. */
export interface BackendEvent {
  nodeId: string;
  label: string;
  status: "running" | "success" | "error";
  seq: number;
  at: string;
  reasoning?: string;
  output?: unknown;
  detail?: string;
}

/** One applicant leg of the backend income result. */
export interface ViewIncomeLeg {
  components: IncomeComponent[];
  thp: number;
}

export interface ViewIncome {
  nasabah: ViewIncomeLeg;
  pasangan?: ViewIncomeLeg;
  total: number;
}

export interface ViewSurvey {
  status: SurveyStatus;
  surveyValue?: number;
  surveyNote?: string;
}

/** One credit-score factor row (mirrors engines/scoring/creditScore factors). */
export interface CreditFactor {
  label: string;
  points: number;
  max: number;
  detail: string;
}

export interface ViewCreditScore {
  score: number;
  grade: string;
  factors: CreditFactor[];
}

export interface ViewCapacity {
  penghasilanBulanan: number;
  dirRate: number;
  kemampuanBayar: number;
}

export interface ViewPlafond {
  ltv: number;
  plafonAgunan: number;
  kebutuhan: number;
  penambahanDp: number;
}

export interface ViewDecision {
  decision: "approved" | "rejected" | "review";
  kemampuanBayar?: number;
  angsuranKpr?: number;
  marginKemampuan?: number;
  score?: number;
  grade?: string;
  reasons?: string[];
}

/** One row of a scheme's installment schedule (fixed → floating). */
export interface ViewScheduleRow {
  fromYear: number;
  toYear: number;
  years: number;
  rate: number;
  angsuran: number;
  floating: boolean;
}

/** One tenor option within a scheme (the backend precomputes the screen's tenors). */
export interface ViewTenorOption {
  tenor: number;
  angsuran: number;
  schedule: ViewScheduleRow[];
  plafonFinal: number;
  tambahanDp: number;
  ok: boolean;
}

export interface ViewOfferingScheme {
  scheme: string;
  label: string;
  rateLabel: string;
  note: string;
  tenorOptions: ViewTenorOption[];
}

export interface ViewOffering {
  maxTenorByAge: number;
  requested: number;
  tenorNasabah: number;
  floatingRate: number;
  schemes: ViewOfferingScheme[];
}

/** Server-built slip↔mutasi reconciliation (ported buildMatch). */
export interface ViewMatching {
  monthlyRecap: MonthlyRecap[];
  incomeTransactions: MatchTxn[];
}

/**
 * The assembled dashboard payload. Many slices are passed through verbatim from
 * the calc/fixture services, so they are loosely typed here (the cards already
 * own their precise shapes); the fields the flow navigates on are typed.
 */
export interface ApplicationView {
  applicationId: string;
  uploads?: string[];
  ocr?: { mutasi?: MutasiExtract; slipRecords?: SlipRecord[] } | null;
  coverage?: unknown;
  fraud?: unknown;
  identity?: unknown;
  slik?: { totalAngsuran?: number; [k: string]: unknown } | null;
  income?: ViewIncome | null;
  capacity?: ViewCapacity | null;
  agunan?: unknown;
  npw?: number | null;
  plafond?: ViewPlafond | null;
  offering?: ViewOffering | null;
  creditScore?: ViewCreditScore | null;
  matching?: ViewMatching | null;
  decision?: ViewDecision | null;
  survey?: ViewSurvey;
}

/** Envelope returned by the BFF process route. */
export interface ProcessResponse {
  ok: boolean;
  applicationId?: string;
  status?: string;
  eventCount?: number;
  view?: ApplicationView;
  events?: BackendEvent[];
  error?: string;
}
