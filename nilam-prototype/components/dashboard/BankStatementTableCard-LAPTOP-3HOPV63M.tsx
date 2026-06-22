"use client";

import { Landmark, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatJuta } from "@/lib/formatRupiah";
import { bankColumnTotal, bankRowTotal } from "@/data/bankStatementFixtures";
import type { NodeStatus } from "@/types/orchestration";
import type { BankStatementRow } from "@/types/profile";

interface BankStatementTableCardProps {
  status: NodeStatus;
  rows: BankStatementRow[];
  /** True when the bank statement was not uploaded. */
  missing?: boolean;
}

/** Column definitions in display order. */
const COLUMNS: { key: keyof Omit<BankStatementRow, "month">; label: string }[] = [
  { key: "salary",    label: "Salary" },
  { key: "thr",       label: "THR" },
  { key: "bonus",     label: "Bonus" },
  { key: "incentive", label: "Incentive" },
  { key: "other",     label: "Other Credits" },
];

const GRID = "grid grid-cols-[64px_repeat(6,1fr)] items-center gap-1";

/** A numeric cell — shows an em dash for zero so the table reads cleanly. */
function Amount({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("text-right tabular-nums", className)}>
      {value === 0 ? <span className="text-bri-muted/40">–</span> : formatJuta(value)}
    </span>
  );
}

/**
 * BankStatementTableCard — "BANK STATEMENT". A month-by-month table of credits
 * detected in the bank statement, with columns Month, Salary, THR, Bonus,
 * Incentive, Other Credits, and Total, plus a column-total footer. Gated until
 * OCR succeeds; shows "belum diunggah" when the document was not uploaded.
 */
export function BankStatementTableCard({ status, rows, missing }: BankStatementTableCardProps) {
  const ready = status === "success" && !missing;
  const grandTotal = rows.reduce((sum, r) => sum + bankRowTotal(r), 0);

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      {/* Header */}
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Landmark size={11} className="text-bri-navy" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
            Bank Statement
          </span>
        </div>
        {ready && (
          <span className="rounded-pill bg-bri-bg px-2 py-0.5 text-[7.5px] font-medium text-bri-muted">
            {rows.length} bulan · nilai dalam juta (jt)
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
      ) : (
        <div className="overflow-hidden rounded-lg border border-bri-line/70">
          {/* Column header */}
          <div
            className={cn(
              GRID,
              "bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.06em] text-bri-muted"
            )}
          >
            <span>Month</span>
            {COLUMNS.map((c) => (
              <span key={c.key} className="text-right">
                {c.label}
              </span>
            ))}
            <span className="text-right">Total</span>
          </div>

          {/* Data rows */}
          <div className="max-h-[190px] overflow-y-auto scroll-thin">
            {rows.map((r) => (
              <div
                key={r.month}
                className={cn(GRID, "border-t border-bri-line/50 px-2 py-1 text-[9px]")}
              >
                <span className="font-medium text-bri-ink">{r.month}</span>
                <Amount value={r.salary} className="text-bri-ink" />
                <Amount value={r.thr} className="text-bri-ink" />
                <Amount value={r.bonus} className="text-bri-ink" />
                <Amount value={r.incentive} className="text-bri-ink" />
                <Amount value={r.other} className="text-bri-ink" />
                <Amount value={bankRowTotal(r)} className="font-bold text-bri-blue" />
              </div>
            ))}
          </div>

          {/* Column totals */}
          <div className={cn(GRID, "border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[9px]")}>
            <span className="font-semibold text-bri-ink">Total</span>
            {COLUMNS.map((c) => (
              <Amount key={c.key} value={bankColumnTotal(c.key)} className="font-semibold text-bri-ink" />
            ))}
            <Amount value={grandTotal} className="font-bold text-bri-navy" />
          </div>
        </div>
      )}
    </div>
  );
}
