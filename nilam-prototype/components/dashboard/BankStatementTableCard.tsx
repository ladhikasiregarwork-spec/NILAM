"use client";

import { Landmark, AlertTriangle, Sparkles } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatJuta, formatRupiah } from "@/lib/formatRupiah";
import { bankColumnTotal, bankRowTotal } from "@/data/bankStatementFixtures";
import type { NodeStatus } from "@/types/orchestration";
import type { BankStatementRow } from "@/types/profile";
import type { MutasiExtract } from "@/types/ocrExtract";

interface BankStatementTableCardProps {
  status: NodeStatus;
  rows: BankStatementRow[];
  missing?: boolean;
  count?: number;
  /** Real transactions parsed from the uploaded statement (when available). */
  mutasi?: MutasiExtract;
}

const COLUMNS: { key: keyof Omit<BankStatementRow, "month">; label: string }[] = [
  { key: "salary",    label: "Salary" },
  { key: "thr",       label: "THR" },
  { key: "bonus",     label: "Bonus" },
  { key: "incentive", label: "Incentive" },
  { key: "other",     label: "Other Credits" },
];

const MOCK_GRID = "grid grid-cols-[64px_repeat(6,1fr)] items-center gap-1";
const TXN_GRID = "grid grid-cols-[58px_1fr_92px_46px_96px] items-center gap-1.5";

function MockAmount({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("text-right tabular-nums", className)}>
      {value === 0 ? <span className="text-bri-muted/40">–</span> : formatJuta(value)}
    </span>
  );
}

/**
 * BankStatementTableCard — "BANK STATEMENT".
 * - When a real statement was parsed (`mutasi`): a transaction table —
 *   Tanggal · Uraian · Klasifikasi · Debit/Kredit · Nominal — with totals.
 * - Otherwise: the mock month-by-month table (fallback).
 */
export function BankStatementTableCard({ status, rows, missing, count, mutasi }: BankStatementTableCardProps) {
  const ready = status === "success" && !missing;
  const hasReal = !!mutasi && (mutasi.transactions?.length ?? 0) > 0;
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
          {!!count && count > 0 && (
            <span className="rounded-pill bg-bri-bg px-1.5 py-px text-[7.5px] font-semibold text-bri-muted">
              {count} file
            </span>
          )}
        </div>
        {ready && hasReal && (
          <span className="flex items-center gap-0.5 rounded-pill bg-bri-navy/10 px-1.5 py-px text-[7.5px] font-semibold text-bri-navy">
            <Sparkles size={8} /> {mutasi!.count} transaksi
            {mutasi!.noRekening ? ` · ${mutasi!.noRekening}` : ""}
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
        /* ── Real transactions ──────────────────────────────────── */
        <>
        {mutasi!.ringkasan && Object.values(mutasi!.ringkasan).some((v) => v > 0) && (
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">Klasifikasi Pemasukan:</span>
            {Object.entries(mutasi!.ringkasan)
              .filter(([, v]) => v > 0)
              .map(([k, v]) => (
                <span key={k} className="rounded-pill bg-emerald-50 px-2 py-0.5 text-[8px] font-semibold text-emerald-700">
                  {k}: {formatRupiah(v)}
                </span>
              ))}
          </div>
        )}
        <div className="overflow-hidden rounded-lg border border-bri-line/70">
          <div className={cn(TXN_GRID, "bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.05em] text-bri-muted")}>
            <span>Tanggal</span>
            <span>Uraian</span>
            <span>Klasifikasi</span>
            <span className="text-center">D/K</span>
            <span className="text-right">Nominal</span>
          </div>
          <div className="max-h-[210px] overflow-y-auto scroll-thin">
            {mutasi!.transactions.map((t, i) => {
              const kredit = t.dk === "Kredit";
              return (
                <div key={i} className={cn(TXN_GRID, "border-t border-bri-line/50 px-2 py-1 text-[8.5px]")}>
                  <span className="tabular-nums text-bri-ink">{t.tanggal}</span>
                  <span className="truncate text-bri-ink" title={t.remark}>{t.remark}</span>
                  <span className="truncate">
                    <span className="rounded-pill bg-bri-bg px-1.5 py-px text-[7px] font-medium text-bri-muted">
                      {t.klasifikasi}
                    </span>
                  </span>
                  <span className={cn("text-center text-[7.5px] font-semibold", kredit ? "text-emerald-600" : "text-red-500")}>
                    {kredit ? "K" : "D"}
                  </span>
                  <span className={cn("text-right tabular-nums font-semibold", kredit ? "text-emerald-600" : "text-red-500")}>
                    {formatRupiah(t.nominal)}
                  </span>
                </div>
              );
            })}
          </div>
          {/* Totals */}
          <div className="grid grid-cols-2 gap-2 border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[8.5px]">
            <span className="font-medium text-emerald-600">
              Total Kredit: <span className="font-bold tabular-nums">{formatRupiah(mutasi!.totalKredit)}</span>
            </span>
            <span className="text-right font-medium text-red-500">
              Total Debet: <span className="font-bold tabular-nums">{formatRupiah(mutasi!.totalDebet)}</span>
            </span>
          </div>
        </div>
        </>
      ) : (
        /* ── Mock month-by-month table (fallback) ───────────────── */
        <div className="overflow-hidden rounded-lg border border-bri-line/70">
          <div className={cn(MOCK_GRID, "bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.06em] text-bri-muted")}>
            <span>Month</span>
            {COLUMNS.map((c) => (
              <span key={c.key} className="text-right">{c.label}</span>
            ))}
            <span className="text-right">Total</span>
          </div>
          <div className="max-h-[190px] overflow-y-auto scroll-thin">
            {rows.map((r) => (
              <div key={r.month} className={cn(MOCK_GRID, "border-t border-bri-line/50 px-2 py-1 text-[9px]")}>
                <span className="font-medium text-bri-ink">{r.month}</span>
                <MockAmount value={r.salary} className="text-bri-ink" />
                <MockAmount value={r.thr} className="text-bri-ink" />
                <MockAmount value={r.bonus} className="text-bri-ink" />
                <MockAmount value={r.incentive} className="text-bri-ink" />
                <MockAmount value={r.other} className="text-bri-ink" />
                <MockAmount value={bankRowTotal(r)} className="font-bold text-bri-blue" />
              </div>
            ))}
          </div>
          <div className={cn(MOCK_GRID, "border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[9px]")}>
            <span className="font-semibold text-bri-ink">Total</span>
            {COLUMNS.map((c) => (
              <MockAmount key={c.key} value={bankColumnTotal(c.key)} className="font-semibold text-bri-ink" />
            ))}
            <MockAmount value={grandTotal} className="font-bold text-bri-navy" />
          </div>
        </div>
      )}
    </div>
  );
}
