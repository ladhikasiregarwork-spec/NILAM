"use client";

import { useMemo, useState } from "react";
import { GitCompareArrows, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import { buildMatch, type MonthlyRecap } from "@/engines/matching/matchSlipMutasi";
import type { NodeStatus } from "@/types/orchestration";
import type { MutasiExtract, SlipGajiExtract } from "@/types/ocrExtract";
import type { ViewMatching } from "@/types/applicationView";

interface MatchingCardProps {
  status: NodeStatus;
  mutasi?: MutasiExtract;
  slip?: SlipGajiExtract;
  missing?: boolean;
  /** Which section to render — recap (Summary Income) or raw transactions. */
  mode?: "rekap" | "transaksi";
  /** Extra content rendered inside this card, below the recap (mode="rekap"). */
  footer?: React.ReactNode;
  /** Authoritative slip↔mutasi reconciliation from nilam_backend; when present
   *  it replaces the client-side buildMatch (server owns the projection). */
  matching?: ViewMatching;
}

const TXN_GRID = "grid grid-cols-[60px_1fr_1fr_1fr_2.2fr] items-center gap-1.5";
// Bulan · Slip[Gaji Pokok, Tunjangan, THR, Bonus, Pend. Lainnya, Potongan, THP] · Mutasi[Gaji, Tunjangan, THR, Bonus, Total Income] · Status
const REC_GRID = "grid grid-cols-[64px_repeat(12,1fr)_58px] items-center gap-1";

/** Editable recap fields (THP & Total Income mutasi are computed, not edited). */
type Field =
  | "gajiPokok" | "tunjangan" | "thr" | "bonus" | "pendapatanLainnya" | "potongan"
  | "gajiMut" | "tunjanganMut" | "thrMut" | "bonusMut";

const SLIP_COLS: { f: Field; label: string }[] = [
  { f: "gajiPokok", label: "Gaji Pokok" },
  { f: "tunjangan", label: "Tunjangan" },
  { f: "thr", label: "THR" },
  { f: "bonus", label: "Bonus" },
  { f: "pendapatanLainnya", label: "Pend. Lainnya" },
  { f: "potongan", label: "Potongan" },
];
const MUT_COLS: { f: Field; label: string }[] = [
  { f: "gajiMut", label: "Gaji" },
  { f: "tunjanganMut", label: "Tunjangan" },
  { f: "thrMut", label: "THR" },
  { f: "bonusMut", label: "Bonus" },
];
const ALL_FIELDS: Field[] = [...SLIP_COLS.map((c) => c.f), ...MUT_COLS.map((c) => c.f)];

/**
 * Per-row OCR default per editable field. Slip uses Upah Pokok + Tunjangan when
 * the OCR reads them; "Pendapatan Lainnya" is the residual of Total Upah (e.g.
 * Bonus Saham, Pendapatan Natura) so the components still sum to the gross.
 * Mutasi credits classify only gaji/THR/bonus, so mutasi tunjangan defaults to 0.
 */
function slipDefault(r: MonthlyRecap, f: Field): number {
  const gross = r.incomeSlip ?? ((r.gajiSlip ?? 0) + (r.potonganSlip ?? 0));
  const tj = r.tunjanganSlip ?? 0;
  const thr = r.thrSlip ?? 0;
  const bonus = r.bonusSlip ?? 0;
  const gp = r.gajiPokokSlip ?? Math.max(0, gross - thr - bonus - tj);
  switch (f) {
    case "gajiPokok": return gp;
    case "tunjangan": return tj;
    case "thr": return thr;
    case "bonus": return bonus;
    case "pendapatanLainnya": return Math.max(0, gross - gp - tj - thr - bonus);
    case "potongan": return r.potonganSlip ?? 0;
    case "gajiMut": return r.gajiMutasi ?? 0;
    case "tunjanganMut": return 0;
    case "thrMut": return r.thrMutasi ?? 0;
    case "bonusMut": return r.bonusMutasi ?? 0;
  }
}

/**
 * MatchingCard — "Matching Salary Slip & Bank Statement". Per-month recap
 * (Income/Potongan/Gaji/THR/Bonus from the SLIP, then Gaji/THR/Bonus from the
 * MUTASI + total mutasi income) above the raw income transactions. Amounts
 * editable; green/red flags whether slip matches mutasi; Status = Edited.
 */
export function MatchingCard({ status, mutasi, slip, missing, mode = "rekap", footer, matching }: MatchingCardProps) {
  const ready = status === "success" && !missing;
  const computed = useMemo(() => buildMatch(mutasi, slip), [mutasi, slip]);
  // Prefer the server's authoritative recap/transactions when a run completed.
  const txns = matching?.incomeTransactions ?? computed.txns;
  const recaps = matching?.monthlyRecap ?? computed.recaps;
  const [edits, setEdits] = useState<Record<string, number>>({});

  // Effective value = edited override, else the OCR default.
  const val = (r: MonthlyRecap, f: Field) => edits[`${r.key}|${f}`] ?? slipDefault(r, f);
  // THP = (gaji pokok + tunjangan + THR + bonus + pendapatan lainnya) − potongan.
  const thpOf = (r: MonthlyRecap) =>
    val(r, "gajiPokok") + val(r, "tunjangan") + val(r, "thr") + val(r, "bonus") + val(r, "pendapatanLainnya") - val(r, "potongan");
  // Total Income mutasi = gaji + tunjangan + THR + bonus.
  const totalMutOf = (r: MonthlyRecap) =>
    val(r, "gajiMut") + val(r, "tunjanganMut") + val(r, "thrMut") + val(r, "bonusMut");
  const isEdited = (r: MonthlyRecap) =>
    ALL_FIELDS.some((f) => {
      const e = edits[`${r.key}|${f}`];
      return e != null && e !== slipDefault(r, f);
    });
  // Matching: THP (slip) vs Gaji (mutasi) — gaji yang masuk rekening ≈ THP.
  const matchColor = (r: MonthlyRecap): string => {
    const a = thpOf(r);
    const b = val(r, "gajiMut");
    if (a <= 0 || b <= 0) return "text-bri-navy";
    return Math.abs(a - b) / Math.max(a, b) <= 0.05 ? "text-emerald-600" : "text-red-500";
  };

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center gap-1">
        <GitCompareArrows size={11} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
          {mode === "transaksi" ? "Transaksi Pemasukan" : "Income Nasabah"}
        </span>
      </div>

      {missing ? (
        <div className="flex h-12 items-center justify-center gap-1.5">
          <AlertTriangle size={14} className="text-amber-500" strokeWidth={2} />
          <span className="text-[9px] font-medium text-amber-600">Butuh Slip Gaji &amp; Mutasi</span>
        </div>
      ) : !ready ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu pemrosesan…</span>
        </div>
      ) : txns.length === 0 ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/50">Tidak ada transaksi Gaji/THR/Bonus terdeteksi</span>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {/* Monthly recap — slip breakdown (THP computed) vs mutasi income */}
          {mode === "rekap" && (
          <div>
            <p className="mb-0.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
              Summary Income <span className="font-normal normal-case text-bri-muted/70">· rincian slip gaji per bulan · nominal bisa diedit · THP otomatis</span>
            </p>
            <div className="overflow-x-auto scroll-thin">
              <div className="min-w-[1200px] overflow-hidden rounded-lg border border-bri-line/70">
                {/* Grouped header — Slip Gaji (7) · Mutasi Rekening (5) */}
                <div className={cn(REC_GRID, "bg-bri-bg/70 px-2 pt-1 text-[6.5px] font-bold uppercase tracking-[0.04em] text-bri-muted")}>
                  <span />
                  <span className="col-span-7 border-l border-bri-line/60 text-center text-bri-navy">Slip Gaji</span>
                  <span className="col-span-5 border-l border-bri-line/60 text-center text-bri-navy">Mutasi Rekening</span>
                  <span />
                </div>
                <div className={cn(REC_GRID, "bg-bri-bg/70 px-2 pb-1 text-[6.5px] font-semibold uppercase tracking-[0.02em] text-bri-muted")}>
                  <span>Bulan</span>
                  {SLIP_COLS.map((c, i) => <span key={c.f} className={cn("text-right", i === 0 && "border-l border-bri-line/60")}>{c.label}</span>)}
                  <span className="text-right font-bold text-bri-navy">THP</span>
                  {MUT_COLS.map((c, i) => <span key={c.f} className={cn("text-right", i === 0 && "border-l border-bri-line/60")}>{c.label}</span>)}
                  <span className="text-right font-bold text-bri-navy">Total Income</span>
                  <span className="text-center">Status</span>
                </div>
                {recaps.map((r) => {
                  const input = (f: Field, leftBorder = false, colorClass = "text-bri-ink") => (
                    <input
                      key={f}
                      type="text"
                      inputMode="numeric"
                      value={val(r, f).toLocaleString("id-ID")}
                      onChange={(e) => setEdits((prev) => ({ ...prev, [`${r.key}|${f}`]: Number(e.target.value.replace(/[^\d]/g, "")) || 0 }))}
                      className={cn(
                        "w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-right text-[7.5px] font-medium tabular-nums hover:border-bri-line focus:border-bri-blue focus:bg-white focus:outline-none",
                        colorClass,
                        leftBorder && "border-l-bri-line/60",
                      )}
                    />
                  );
                  return (
                    <div key={r.key} className={cn(REC_GRID, "border-t border-bri-line/50 px-2 py-1 text-[8.5px]")}>
                      <span className="flex min-w-0 flex-col">
                        <span className="font-medium text-bri-ink">{r.bulan}</span>
                        {r.tglBayarSlip && (
                          <span className="truncate text-[6px] text-bri-muted" title={r.tglBayarSlip}>slip: {r.tglBayarSlip}</span>
                        )}
                      </span>
                      {SLIP_COLS.map((c, i) => input(c.f, i === 0))}
                      <span className={cn("px-1 text-right text-[7.5px] font-bold tabular-nums", matchColor(r))} title="THP = (Gaji Pokok + Tunjangan + THR + Bonus + Pend. Lainnya) − Potongan · dicocokkan dengan Gaji mutasi">{formatRupiah(thpOf(r))}</span>
                      {MUT_COLS.map((c, i) => input(c.f, i === 0, c.f === "gajiMut" ? cn(matchColor(r), "font-semibold") : "text-bri-ink"))}
                      <span className="px-1 text-right text-[7.5px] font-bold tabular-nums text-bri-navy" title="Total Income = Gaji + Tunjangan + THR + Bonus (mutasi)">{formatRupiah(totalMutOf(r))}</span>
                      <span className="flex justify-center">
                        <span className={cn("rounded-pill px-1.5 py-px text-[7px] font-semibold", isEdited(r) ? "bg-amber-100 text-amber-700" : "bg-bri-bg text-bri-muted")}>
                          {isEdited(r) ? "Edited" : "Non-edited"}
                        </span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
            <p className="mt-0.5 text-[7px] text-bri-muted/70">
              <b>THP = (Gaji Pokok + Tunjangan + THR + Bonus + Pend. Lainnya) − Potongan.</b> Pend. Lainnya = sisa Total Upah (mis. Bonus Saham, Pendapatan Natura). Upah Pokok &amp; Tunjangan diisi dari OCR bila terbaca.
              Matching: <span className="text-emerald-600">hijau</span> = <b>THP cocok dengan Gaji (mutasi)</b>, <span className="text-red-500">merah</span> = selisih (gaji yang masuk rekening ≈ THP).
            </p>
          </div>
          )}

          {/* Income transactions */}
          {mode === "transaksi" && (
          <div>
            <p className="mb-0.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
              Transaksi Pemasukan (dari Mutasi)
            </p>
            <div className="overflow-hidden rounded-lg border border-bri-line/70">
              <div className={cn(TXN_GRID, "bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.05em] text-bri-muted")}>
                <span>Tgl Mutasi</span>
                <span className="text-right">Gaji</span>
                <span className="text-right">THR</span>
                <span className="text-right">Bonus</span>
                <span>Remark</span>
              </div>
              <div className="max-h-[130px] overflow-y-auto scroll-thin">
                {txns.map((t, i) => (
                  <div key={i} className={cn(TXN_GRID, "border-t border-bri-line/50 px-2 py-1 text-[8.5px]")}>
                    <span className="tabular-nums text-bri-ink">{t.tanggal}</span>
                    <span className="text-right tabular-nums text-emerald-600">{t.gaji ? formatRupiah(t.gaji) : "–"}</span>
                    <span className="text-right tabular-nums text-bri-ink">{t.thr ? formatRupiah(t.thr) : "–"}</span>
                    <span className="text-right tabular-nums text-bri-ink">{t.bonus ? formatRupiah(t.bonus) : "–"}</span>
                    <span className="truncate text-bri-muted" title={t.remark}>{t.remark}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          )}
        </div>
      )}

      {/* Perhitungan Kemampuan Bayar — di dalam kartu Income Nasabah */}
      {mode === "rekap" && footer && (
        <div className="mt-3 border-t border-bri-line pt-3">{footer}</div>
      )}
    </div>
  );
}
