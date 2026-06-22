/**
 * Customer-dossier types — the data surfaced by the three "customer profile"
 * cards added to the dashboard:
 *
 *   1. CustomerProfile     → CustomerProfileCard      (identity + employment summary)
 *   2. MutationRecord      → MutationRecordCard       (credits seen in bank mutation)
 *   3. EmploymentAgreement → EmploymentAgreementCard  (perjanjian kerja)
 *
 * These are kept separate from `types/engines.ts` so the future API swap has a
 * single, well-typed contract to fulfil. A real backend just has to return these
 * shapes; the cards never need to change.
 */

/** Basic KYC identity plus a short employment summary (from KTP + HR data). */
export interface CustomerProfile {
  nik: string;
  nama: string;
  gender: string;
  /** Display string, e.g. "08/11/1988". */
  tanggalLahir: string;
  perusahaan: string;
  jabatan: string;
}

/** One credit category detected in the account mutation (mutasi rekening). */
export interface MutationCredit {
  /** Human label, e.g. "Gaji", "THR", "Transfer Masuk Lain". */
  label: string;
  /** Bucketing so the UI can colour/group: salary, THR, bonus, or anything else. */
  category: "salary" | "thr" | "bonus" | "other";
  /** Number of matching transactions across the period. */
  count: number;
  /** Total Rupiah credited across the period. */
  sum: number;
  /** Smallest single matching credit (used as the conservative "min"). */
  min: number;
}

/** All credits observed in the customer's bank mutation over a period. */
export interface MutationRecord {
  /** Human-readable coverage, e.g. "Apr 2025 – Mar 2026". */
  periodLabel: string;
  credits: MutationCredit[];
}

/** Profile extracted from the employment agreement (perjanjian kerja). */
export interface EmploymentAgreement {
  perusahaan: string;
  jabatan: string;
  /** e.g. "Karyawan Tetap" | "Kontrak (PKWT)". */
  statusKepegawaian: string;
  /** Tenure as a display string, e.g. "5 tahun 3 bulan". */
  masaKerja: string;
  /** Contractual base salary (gaji pokok). */
  gajiPokok: number;
  /** Contract start, e.g. "01/02/2021". */
  tanggalMulai: string;
  /** Contract end, e.g. "31/01/2026" or "Tetap" for permanent staff. */
  tanggalBerakhir: string;
}

/** One member listed on the family card (Kartu Keluarga). */
export interface FamilyMember {
  nama: string;
  /** Relationship to the head of family, e.g. "Kepala Keluarga", "Istri", "Anak". */
  hubungan: string;
}

/** Profile extracted from the family card (Kartu Keluarga / KK). */
export interface KartuKeluarga {
  nomorKK: string;
  kepalaKeluarga: string;
  alamat: string;
  members: FamilyMember[];
}

/**
 * One month of credits observed in the bank statement (mutasi rekening),
 * broken out by category. `total` is the sum of all credit columns.
 */
export interface BankStatementRow {
  /** Display month, e.g. "Apr 2025". */
  month: string;
  salary: number;
  thr: number;
  bonus: number;
  incentive: number;
  /** Any other incoming credit (transfers, refunds, etc.). */
  other: number;
}

/** One credit facility reported by SLIK OJK (a loan the customer has/had). */
export interface SlikLoan {
  /** Facility type, e.g. "KPR", "KKB", "Kartu Kredit", "KTA". */
  jenis: string;
  /** Reporting lender, e.g. "Bank BRI". */
  lembaga: string;
  /** Approved limit (plafon). */
  plafon: number;
  /** Outstanding balance (baki debet). */
  baki: number;
  /** Monthly installment. */
  angsuran: number;
  /** Collectibility status, e.g. "Lancar". */
  status: string;
  /** Collectibility class 1..5 (kolektibilitas). */
  kualitas: number;
}
