export type FlowStep =
  | "opening"
  | "income_type"
  | "joint_income"
  | "requirement"
  | "processing"
  | "analyst_decision";

export interface PersonaConfig {
  nasabahPayroll: boolean;
  pasanganPayroll: boolean;
}
