import type { MutasiExtract, SlipGajiExtract } from "@/types/ocrExtract";

/** One income transaction matched from the bank statement. */
export interface MatchTxn {
  tanggal: string;
  gaji: number;
  thr: number;
  bonus: number;
  remark: string;
}

/** Per-month recap, combining bank-statement income and slip figures. */
export interface MonthlyRecap {
  key: string; // "MM/YY"
  bulan: string; // "Apr 2026"
  // ── From the bank statement (mutasi), classified credits ──
  gajiMutasi: number;
  thrMutasi: number;
  bonusMutasi: number;
  // ── From the salary slip of that month ──
  /** Take-home pay (THP) from the slip. */
  gajiSlip?: number;
  thrSlip?: number;
  bonusSlip?: number;
  /** Total Upah (gross income) from the slip. */
  incomeSlip?: number;
  /** Upah/Gaji Pokok from the slip (when OCR reads it). */
  gajiPokokSlip?: number;
  /** Sum of "Tunjangan ..." earning lines from the slip (excl. THR). */
  tunjanganSlip?: number;
  /** Total Potongan (full deductions) from the slip. */
  potonganSlip?: number;
  /** Net deductions = Total Potongan − potongan(bonus + THR + cuti). */
  potonganNet?: number;
  /** Raw payment date printed on the slip ("25.05.2026"), when matched. */
  tglBayarSlip?: string;
}

export interface MatchResult {
  txns: MatchTxn[];
  recaps: MonthlyRecap[];
}

const MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const MONTH_NAMES: Record<string, number> = {
  jan: 1, januari: 1, january: 1, feb: 2, februari: 2, february: 2, mar: 3, maret: 3, march: 3,
  apr: 4, april: 4, mei: 5, may: 5, jun: 6, juni: 6, june: 6, jul: 7, juli: 7, july: 7,
  agu: 8, agustus: 8, aug: 8, august: 8, sep: 9, september: 9, okt: 10, oktober: 10, oct: 10, october: 10,
  nov: 11, november: 11, des: 12, desember: 12, dec: 12, december: 12,
};

function mutasiMonthKey(tgl: string): string {
  const p = tgl.split("/"); // DD MM YY
  return p.length === 3 ? `${p[1]}/${p[2]}` : tgl;
}

function monthLabel(key: string): string {
  const [mm, yy] = key.split("/");
  return `${MONTHS_ID[Number(mm) - 1] ?? mm} 20${yy}`;
}

function slipMonthKey(s?: string): string | undefined {
  if (!s) return undefined;
  // Full date DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY (BRI slip: "25.05.2026").
  const full = s.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})/);
  if (full) return `${full[2].padStart(2, "0")}/${full[3].slice(-2)}`;
  const named = s.match(/([A-Za-z]+)\s+(\d{4})/);
  if (named) {
    const num = MONTH_NAMES[named[1].toLowerCase()];
    if (num) return `${String(num).padStart(2, "0")}/${named[2].slice(2)}`;
  }
  const numeric = s.match(/(\d{1,2})[./-](\d{2,4})/);
  if (numeric) return `${numeric[1].padStart(2, "0")}/${numeric[2].slice(-2)}`;
  return undefined;
}

const keyOrder = (k: string) => {
  const [mm, yy] = k.split("/").map(Number);
  return (yy || 0) * 100 + (mm || 0);
};
const txnOrder = (t: string) => {
  const [dd, mm, yy] = t.split("/").map(Number);
  return (yy || 0) * 10000 + (mm || 0) * 100 + (dd || 0);
};

/**
 * Match the bank statement's income transactions (Gaji/THR/Bonus credits) with
 * the salary slip(s): a transaction list and a per-month recap that pairs the
 * statement income with the slip's Total Upah / Total Potongan.
 */
export function buildMatch(mutasi?: MutasiExtract, slip?: SlipGajiExtract): MatchResult {
  const txns: MatchTxn[] = [];
  for (const t of mutasi?.transactions ?? []) {
    if (t.dk !== "Kredit") continue;
    const k = t.klasifikasi;
    if (k === "Gaji" || k === "THR" || k === "Bonus") {
      txns.push({
        tanggal: t.tanggal,
        gaji: k === "Gaji" ? t.nominal : 0,
        thr: k === "THR" ? t.nominal : 0,
        bonus: k === "Bonus" ? t.nominal : 0,
        remark: t.remark,
      });
    }
  }

  const map = new Map<string, MonthlyRecap>();
  const ensure = (key: string): MonthlyRecap => {
    let r = map.get(key);
    if (!r) {
      r = { key, bulan: monthLabel(key), gajiMutasi: 0, thrMutasi: 0, bonusMutasi: 0 };
      map.set(key, r);
    }
    return r;
  };

  for (const t of txns) {
    const r = ensure(mutasiMonthKey(t.tanggal));
    r.gajiMutasi += t.gaji;
    r.thrMutasi += t.thr;
    r.bonusMutasi += t.bonus;
  }
  for (const rec of slip?.records ?? []) {
    const key = slipMonthKey(rec.tanggalPembayaran);
    if (!key) continue;
    const r = ensure(key);
    if (rec.thp != null) r.gajiSlip = (r.gajiSlip ?? 0) + rec.thp; // THP ↔ gaji mutasi
    if (rec.thr != null) r.thrSlip = (r.thrSlip ?? 0) + rec.thr;
    if (rec.bonus != null) r.bonusSlip = (r.bonusSlip ?? 0) + rec.bonus;
    if (rec.gajiPokok != null) r.gajiPokokSlip = (r.gajiPokokSlip ?? 0) + rec.gajiPokok;
    if (rec.tunjangan != null) r.tunjanganSlip = (r.tunjanganSlip ?? 0) + rec.tunjangan;
    if (rec.totalUpah != null) r.incomeSlip = (r.incomeSlip ?? 0) + rec.totalUpah;
    if (rec.totalPotongan != null) {
      r.potonganSlip = (r.potonganSlip ?? 0) + rec.totalPotongan;
      const net = rec.totalPotongan - (rec.potonganBonus ?? 0) - (rec.potonganThr ?? 0) - (rec.potonganCuti ?? 0);
      r.potonganNet = (r.potonganNet ?? 0) + net;
    }
    if (rec.tanggalPembayaran) r.tglBayarSlip = rec.tanggalPembayaran;
  }

  return {
    txns: txns.sort((a, b) => txnOrder(a.tanggal) - txnOrder(b.tanggal)),
    recaps: [...map.values()].sort((a, b) => keyOrder(a.key) - keyOrder(b.key)),
  };
}
