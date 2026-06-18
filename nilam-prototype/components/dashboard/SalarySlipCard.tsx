"use client";

import { FileText, AlertTriangle, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import type { NodeStatus } from "@/types/orchestration";
import type { IncomeComponent } from "@/types/income";
import type { SlipGajiExtract } from "@/types/ocrExtract";

interface SalarySlipCardProps {
  status: NodeStatus;
  /** Mock base salary (fallback when no real slip read). */
  gajiPokok: number;
  /** Mock components (fallback). */
  components: IncomeComponent[];
  missing?: boolean;
  /** Real OCR-extracted slip records (one per payment date). */
  extracted?: SlipGajiExtract;
  /** How many slip files uploaded. */
  count?: number;
}

const fmt = (n?: number) => (n == null ? "—" : formatRupiah(n));

const SLIP_GRID = "grid grid-cols-[96px_repeat(5,1fr)] items-center gap-1.5";

/**
 * SalarySlipCard — "SALARY SLIP". When real slips were read (`extracted`):
 * a per-payment-date table — Tanggal Pembayaran, Total Upah, Total Potongan,
 * THP (= upah − potongan), THR, Bonus. Otherwise falls back to mock components.
 */
export function SalarySlipCard({ status, gajiPokok, components, missing, extracted, count }: SalarySlipCardProps) {
  const ready = status === "success" && !missing;
  const records = extracted?.records ?? [];
  const hasReal = records.length > 0;

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center justify-between gap-1">
        <div className="flex items-center gap-1">
          <FileText size={11} className="text-bri-navy" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">Salary Slip</span>
          {!!count && count > 0 && (
            <span className="rounded-pill bg-bri-bg px-1.5 py-px text-[7.5px] font-semibold text-bri-muted">{count} file</span>
          )}
        </div>
        {ready && hasReal && (
          <span className="flex items-center gap-0.5 rounded-pill bg-bri-navy/10 px-1.5 py-px text-[7.5px] font-semibold text-bri-navy">
            <Sparkles size={8} /> Hasil OCR · per tanggal
          </span>
        )}
      </div>

      {missing ? (
        <div className="flex h-12 items-center justify-center gap-1.5">
          <AlertTriangle size={14} className="text-amber-500" strokeWidth={2} />
          <span className="text-[9px] font-medium text-amber-600">Dokumen belum diunggah</span>
        </div>
      ) : !ready ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu pemrosesan…</span>
        </div>
      ) : hasReal ? (
        /* ── Per payment date ───────────────────────────────────── */
        <div className="overflow-hidden rounded-lg border border-bri-line/70">
          <div className={cn(SLIP_GRID, "bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.05em] text-bri-muted")}>
            <span>Tgl Pembayaran</span>
            <span className="text-right">Total Upah</span>
            <span className="text-right">Potongan</span>
            <span className="text-right">THP</span>
            <span className="text-right">THR</span>
            <span className="text-right">Bonus</span>
          </div>
          <div className="max-h-[200px] overflow-y-auto scroll-thin">
            {records.map((r, i) => (
              <div key={i} className={cn(SLIP_GRID, "border-t border-bri-line/50 px-2 py-1 text-[9px]")}>
                <span className="font-medium text-bri-ink">{r.tanggalPembayaran ?? "—"}</span>
                <span className="text-right tabular-nums text-bri-ink">{fmt(r.totalUpah)}</span>
                <span className="text-right tabular-nums text-red-500">{fmt(r.totalPotongan)}</span>
                <span className="text-right font-bold tabular-nums text-bri-blue">{fmt(r.thp)}</span>
                <span className="text-right tabular-nums text-bri-ink">{fmt(r.thr)}</span>
                <span className="text-right tabular-nums text-bri-ink">{fmt(r.bonus)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[8px] text-bri-muted">
            THP = Total Upah − Total Potongan · {records.length} slip
          </div>
        </div>
      ) : (
        /* ── Mock fallback ──────────────────────────────────────── */
        <div className="flex items-stretch gap-3">
          <div className="flex w-[200px] shrink-0 flex-col justify-center rounded-lg border border-bri-line/70 bg-bri-bg/50 px-3 py-2">
            <span className="text-[8.5px] text-bri-muted">Gaji Pokok</span>
            <span className="text-[18px] font-bold leading-tight text-bri-navy tabular-nums">{formatRupiah(gajiPokok)}</span>
            <span className="text-[8px] text-bri-muted">per bulan</span>
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">Komponen Penghasilan (rata-rata)</span>
            <div className="mt-1 grid grid-cols-4 gap-2">
              {components.map((c) => (
                <div key={c.key} className="flex flex-col rounded-lg border border-bri-line/70 px-2 py-1.5">
                  <span className="text-[8px] text-bri-muted">{c.key}</span>
                  <span className="text-[11px] font-bold text-bri-blue tabular-nums">{formatRupiah(c.avg)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
