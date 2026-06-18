/**
 * KPR credit score (0–100) from the borrower's profile + the deal ratios:
 * pendidikan, status kawin, usia, kepemilikan simpanan BRI, jangka waktu,
 * % uang muka, jumlah tanggungan, rasio gaji/angsuran, rasio harga/plafond.
 */
export interface CreditScoreInput {
  pendidikan?: string;
  statusKawin?: string;
  usia?: number;
  /** Owns a BRI savings account. */
  punyaSimpananBri?: boolean;
  /** Desired loan tenor in years. */
  jangkaWaktu?: number;
  hargaRumah?: number;
  uangMuka?: number;
  jumlahTanggungan?: number;
  /** Monthly income (THP / gaji). */
  incomeMonthly?: number;
  /** Total monthly installment (KPR + existing SLIK). */
  angsuranBulanan?: number;
  /** Financed amount = harga − uang muka. */
  plafond?: number;
}

export interface ScoreFactor {
  label: string;
  points: number;
  max: number;
  detail: string;
}

export interface CreditScoreResult {
  score: number; // 0–100
  grade: string;
  factors: ScoreFactor[];
}

function pendidikanPts(p?: string): number {
  switch ((p ?? "").toUpperCase()) {
    case "S3":
    case "S2":
      return 10;
    case "S1":
    case "D3":
      return 8;
    case "SMA/SMK":
    case "SMA":
      return 6;
    case "SMP":
      return 4;
    case "SD":
      return 2;
    default:
      return 3;
  }
}

function kawinPts(s?: string): number {
  const l = (s ?? "").toLowerCase();
  if (l.includes("belum")) return 3;
  if (l.includes("cerai")) return 2;
  if (l.includes("kawin")) return 5;
  return 2;
}

function usiaPts(a?: number): number {
  if (a == null) return 4;
  if (a >= 30 && a <= 45) return 10;
  if (a >= 25 && a < 30) return 8;
  if (a > 45 && a <= 52) return 7;
  if (a >= 21 && a < 25) return 5;
  if (a > 52 && a <= 56) return 4;
  return 2;
}

function tenorPts(y?: number): number {
  if (y == null) return 4;
  if (y <= 10) return 10;
  if (y <= 15) return 8;
  if (y <= 20) return 6;
  return 4;
}

function tanggunganPts(n?: number): number {
  if (n == null) return 6;
  if (n === 0) return 10;
  if (n <= 2) return 8;
  if (n <= 4) return 5;
  return 2;
}

export function computeCreditScore(inp: CreditScoreInput): CreditScoreResult {
  const pPts = pendidikanPts(inp.pendidikan);
  const kPts = kawinPts(inp.statusKawin);
  const uPts = usiaPts(inp.usia);
  const briPts = inp.punyaSimpananBri ? 10 : 0;
  const tPts = tenorPts(inp.jangkaWaktu);

  const dpRatio =
    inp.hargaRumah && inp.uangMuka != null && inp.hargaRumah > 0 ? inp.uangMuka / inp.hargaRumah : undefined;
  const dpPts = dpRatio == null ? 4 : Math.round(Math.max(0, Math.min(1, dpRatio / 0.3)) * 15);

  const tgPts = tanggunganPts(inp.jumlahTanggungan);

  const giRatio =
    inp.incomeMonthly && inp.angsuranBulanan && inp.angsuranBulanan > 0
      ? inp.incomeMonthly / inp.angsuranBulanan
      : undefined;
  const giPts =
    giRatio == null ? 8 : giRatio >= 3 ? 20 : giRatio >= 2 ? 15 : giRatio >= 1.5 ? 10 : giRatio >= 1 ? 6 : 2;

  const hpRatio = inp.hargaRumah && inp.plafond && inp.plafond > 0 ? inp.hargaRumah / inp.plafond : undefined;
  const hpPts = hpRatio == null ? 4 : hpRatio >= 1.43 ? 10 : hpRatio >= 1.25 ? 8 : hpRatio >= 1.1 ? 5 : 3;

  const score = Math.max(0, Math.min(100, pPts + kPts + uPts + briPts + tPts + dpPts + tgPts + giPts + hpPts));
  const grade =
    score >= 80 ? "A · Sangat Baik" : score >= 65 ? "B · Baik" : score >= 50 ? "C · Cukup" : "D · Kurang";

  return {
    score,
    grade,
    factors: [
      { label: "Pendidikan", points: pPts, max: 10, detail: inp.pendidikan ?? "—" },
      { label: "Status Kawin", points: kPts, max: 5, detail: inp.statusKawin ?? "—" },
      { label: "Usia", points: uPts, max: 10, detail: inp.usia != null ? `${inp.usia} th` : "—" },
      { label: "Simpanan BRI", points: briPts, max: 10, detail: inp.punyaSimpananBri ? "Ya" : "Tidak" },
      { label: "Jangka Waktu", points: tPts, max: 10, detail: inp.jangkaWaktu != null ? `${inp.jangkaWaktu} th` : "—" },
      { label: "Uang Muka", points: dpPts, max: 15, detail: dpRatio != null ? `${Math.round(dpRatio * 100)}%` : "—" },
      { label: "Tanggungan", points: tgPts, max: 10, detail: inp.jumlahTanggungan != null ? `${inp.jumlahTanggungan} org` : "—" },
      { label: "Gaji / Angsuran", points: giPts, max: 20, detail: giRatio != null ? `${giRatio.toFixed(1)}×` : "—" },
      { label: "Harga / Plafond", points: hpPts, max: 10, detail: hpRatio != null ? `${hpRatio.toFixed(2)}×` : "—" },
    ],
  };
}
