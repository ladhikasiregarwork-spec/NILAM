export type FlowStep =
  | "opening"
  | "term_condition"
  | "income_type"
  | "joint_income"
  | "requirement"
  | "data_diri"
  | "agunan"
  | "processing"
  | "survey"
  | "offering"
  | "disburse"
  | "analyst_decision";

export interface PersonaConfig {
  nasabahPayroll: boolean;
  pasanganPayroll: boolean;
}

/**
 * Survey status for collateral worth ≥ SURVEY_THRESHOLD. Such applications go to
 * a Relationship Manager (RM) for an on-site survey before the offer is released.
 *   none     — not applicable (price below threshold or not yet submitted)
 *   pending  — waiting in the RM survey queue
 *   approved — RM finished the survey & approved (offer released, RM's appraised value used)
 *   rejected — RM finished the survey & rejected
 */
export type SurveyStatus = "none" | "pending" | "approved" | "rejected";

/** Collateral price at/above which an RM survey is required before an offer. */
export const SURVEY_THRESHOLD = 500_000_000;
