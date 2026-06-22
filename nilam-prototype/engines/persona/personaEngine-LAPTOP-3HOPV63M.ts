import type { FlowStep, PersonaConfig } from "@/types/flow";

/**
 * The customer flow (Image 1):
 *   opening (masuk aplikasi) → requirement (upload 5 dokumen)
 *   → processing (identifikasi data) → analyst_decision (menunggu feedback)
 *
 * Income-type and joint-income steps were removed: the document-upload flow is
 * single-applicant and document-centric.
 */
export function planFlow(_p?: PersonaConfig): FlowStep[] {
  return ["opening", "requirement", "processing", "analyst_decision"];
}
