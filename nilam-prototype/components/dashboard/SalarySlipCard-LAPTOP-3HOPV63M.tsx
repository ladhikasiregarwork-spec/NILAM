"use client";

import { FileText, AlertTriangle } from "lucide-react";
import { formatRupiah } from "@/lib/formatRupiah";
import type { NodeStatus } from "@/types/orchestration";
import type { IncomeComponent } from "@/types/income";

interface SalarySlipCardProps {
  status: NodeStatus;
  /** Base salary (gaji pokok) from the salary slip. */
  gajiPokok: number;
  /** Income components extracted alongside the slip (avg monthly nominal). */
  components: IncomeComponent[];
  /** True when the salary slip was not uploaded. */
  missing?: boolean;
}

/**
 * SalarySlipCard — "SALARY SLIP". Full-width section: base salary headline plus
 * the extracted income components (Gaji, THR, Bonus, Insentif). Gated until OCR
 * succeeds.
 */
export function SalarySlipCard({ status, gajiPokok, components, missing }: SalarySlipCardProps) {
  const ready = status === "success" && !missing;

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center gap-1">
        <FileText size={11} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
          Salary Slip
        </span>
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
      ) : (
        <div className="flex items-stretch gap-3">
          {/* Gaji Pokok hero */}
          <div className="flex w-[200px] shrink-0 flex-col justify-center rounded-lg border border-bri-line/70 bg-bri-bg/50 px-3 py-2">
            <span className="text-[8.5px] text-bri-muted">Gaji Pokok</span>
            <span className="text-[18px] font-bold leading-tight text-bri-navy tabular-nums">
              {formatRupiah(gajiPokok)}
            </span>
            <span className="text-[8px] text-bri-muted">per bulan</span>
          </div>

          {/* Components breakdown */}
          <div className="min-w-0 flex-1">
            <span className="text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
              Komponen Penghasilan (rata-rata)
            </span>
            <div className="mt-1 grid grid-cols-4 gap-2">
              {components.map((c) => (
                <div
                  key={c.key}
                  className="flex flex-col rounded-lg border border-bri-line/70 px-2 py-1.5"
                >
                  <span className="text-[8px] text-bri-muted">{c.key}</span>
                  <span className="text-[11px] font-bold text-bri-blue tabular-nums">
                    {formatRupiah(c.avg)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
