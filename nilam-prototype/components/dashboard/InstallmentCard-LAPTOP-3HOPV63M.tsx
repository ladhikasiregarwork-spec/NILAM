"use client";

import { Calculator } from "lucide-react";
import { formatRupiah } from "@/lib/formatRupiah";
import { computeThp } from "@/engines/thp/thpEngine";
import type { NodeStatus } from "@/types/orchestration";
import type { CustomerIncome } from "@/types/income";

interface InstallmentCardProps {
  status: NodeStatus;
  /** Customer income (weighted components feed the capacity calc). */
  income: CustomerIncome;
  /** Existing total monthly installment from SLIK. */
  totalAngsuran: number;
}

/** Debt-Service-Ratio cap used for the installment-capacity calculation. */
const DSR = 0.5;

/** Label / value row. */
function Row({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[9px] text-white/70">{label}</span>
      <span className={`tabular-nums ${strong ? "text-[11px] font-bold text-white" : "text-[10px] font-medium text-white/90"}`}>
        {value}
      </span>
    </div>
  );
}

/**
 * InstallmentCard — "Calculate installment payments". Computes the customer's
 * new-installment capacity from weighted income (DSR cap) minus existing SLIK
 * installments. Premium navy treatment (this is the final output). Gated until
 * the THP step succeeds.
 */
export function InstallmentCard({ status, income, totalAngsuran }: InstallmentCardProps) {
  const ready = status === "success";

  const gross = computeThp(income).grossBeforeAngsuran;
  const maxTotal = Math.round(gross * DSR);
  const available = Math.max(maxTotal - totalAngsuran, 0);

  return (
    <div
      className="rounded-xl border border-bri-navy/30 px-3 py-2.5 shadow-soft"
      style={{ background: "linear-gradient(135deg, #00305C 0%, #00529C 100%)" }}
    >
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Calculator size={11} className="text-white" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-white/80">
            Calculate Installment Payments
          </span>
        </div>
        <span className="rounded-pill bg-white/15 px-2 py-0.5 text-[7.5px] font-semibold text-white/90">
          DSR {Math.round(DSR * 100)}%
        </span>
      </div>

      {!ready ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[10px] italic text-white/50">Menunggu perhitungan…</span>
        </div>
      ) : (
        <div className="flex items-stretch gap-3">
          {/* Hero — maximum new installment */}
          <div className="flex w-[230px] shrink-0 flex-col justify-center rounded-lg bg-white/10 px-3 py-2">
            <span className="text-[9px] text-white/70">Maksimal Angsuran Baru</span>
            <span className="text-[24px] font-bold leading-tight text-white tabular-nums">
              {formatRupiah(available)}
            </span>
            <span className="text-[8px] text-white/60">per bulan</span>
          </div>

          {/* Breakdown */}
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-1.5">
            <Row label="Penghasilan Tertimbang" value={formatRupiah(gross)} />
            <Row label={`Maks. Total Angsuran (DSR ${Math.round(DSR * 100)}%)`} value={formatRupiah(maxTotal)} />
            <Row label="Angsuran Berjalan (SLIK)" value={`− ${formatRupiah(totalAngsuran)}`} />
            <div className="my-0.5 border-t border-white/20" />
            <Row label="Maksimal Angsuran Baru" value={formatRupiah(available)} strong />
          </div>
        </div>
      )}
    </div>
  );
}
