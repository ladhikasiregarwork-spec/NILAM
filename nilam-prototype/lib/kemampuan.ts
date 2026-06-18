import type { OcrResults } from "@/types/ocrExtract";

/** Monthly income components used for the payment-capacity formula. */
export interface IncomeParts {
  gajiBulanan: number;
  thrTahunan: number;
  bonusTahunan: number;
}

/** Derive gaji/THR/bonus from the bank-statement (mutasi) classification. */
export function incomePartsFromOcr(ocr: OcrResults): IncomeParts {
  const gajiBulanan =
    ocr.mutasi?.gajiNominal ?? ocr.slipGaji?.records?.find((r) => r.thp != null)?.thp ?? 0;
  return {
    gajiBulanan,
    thrTahunan: ocr.mutasi?.ringkasan?.THR ?? 0,
    bonusTahunan: ocr.mutasi?.ringkasan?.Bonus ?? 0,
  };
}

/** Gross monthly income = gaji/bulan + THR/12 + bonus/12. */
export function penghasilanBulanan(gajiBulanan: number, thrTahunan: number, bonusTahunan: number): number {
  return gajiBulanan + thrTahunan / 12 + bonusTahunan / 12;
}

/** Debt-to-Income Ratio by monthly income: <15jt 50% · 15–25jt 55% · >25jt 60%. */
export function dirRate(penghasilan: number): number {
  if (penghasilan < 15_000_000) return 0.5;
  if (penghasilan <= 25_000_000) return 0.55;
  return 0.6;
}

/**
 * Payment capacity = (gaji/bulan + THR/12 + bonus/12 − angsuran SLIK) × DIR,
 * where DIR is set by the monthly income band.
 */
export function kemampuanBayar(
  gajiBulanan: number,
  thrTahunan: number,
  bonusTahunan: number,
  slikAngsuran: number,
): number {
  const penghasilan = penghasilanBulanan(gajiBulanan, thrTahunan, bonusTahunan);
  return Math.round((penghasilan - slikAngsuran) * dirRate(penghasilan));
}
