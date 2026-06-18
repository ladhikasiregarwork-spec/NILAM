import type { FlowStep, PersonaConfig } from "@/types/flow";

/**
 * The customer KPR flow:
 *   opening → term_condition (S&K) → requirement (upload dokumen)
 *   → data_diri (form data diri, prefilled dari OCR) → agunan → processing
 *   → survey (hanya bila agunan ≥ Rp500jt — disurvey Relationship Manager)
 *   → offering (penawaran KPR) → disburse (pencairan)
 *
 * `survey` selalu ada di urutan agar bisa di-navigasi; untuk agunan < Rp500jt
 * langkah ini dilewati (processing → offering langsung).
 */
export function planFlow(_p?: PersonaConfig): FlowStep[] {
  return ["opening", "term_condition", "requirement", "data_diri", "agunan", "processing", "survey", "offering", "disburse"];
}
