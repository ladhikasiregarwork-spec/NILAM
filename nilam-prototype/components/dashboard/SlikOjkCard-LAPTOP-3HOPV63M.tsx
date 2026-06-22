"use client";

import { Landmark, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import type { NodeStatus } from "@/types/orchestration";
import type { SlikLoan } from "@/types/profile";

interface SlikOjkCardProps {
  status: NodeStatus;
  loans: SlikLoan[];
  totalAngsuran: number;
  /** Credit score from the bureau pull. */
  score: number;
}

/**
 * SlikOjkCard — "SLIK OJK (every loan user ever have)". Full-width table of all
 * credit facilities reported by SLIK, with total monthly installment and credit
 * score. Gated until the SLIK retrieval step succeeds.
 */
export function SlikOjkCard({ status, loans, totalAngsuran, score }: SlikOjkCardProps) {
  const ready = status === "success";

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      {/* Header */}
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Landmark size={11} className="text-bri-navy" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
            SLIK OJK · Riwayat Kredit
          </span>
        </div>
        {ready && (
          <div className="flex items-center gap-1 rounded-pill bg-bri-bg px-2 py-0.5">
            <ShieldCheck size={9} className="text-emerald-500" strokeWidth={2.5} />
            <span className="text-[8px] text-bri-muted">Score</span>
            <span className="text-[11px] font-bold text-bri-navy">{score}</span>
          </div>
        )}
      </div>

      {!ready ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu SLIK…</span>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-bri-line/70">
          {/* Column header */}
          <div className="grid grid-cols-[1.1fr_1.1fr_1fr_1fr_1fr_auto] items-center gap-2 bg-bri-bg/70 px-2 py-1 text-[7.5px] font-semibold uppercase tracking-[0.06em] text-bri-muted">
            <span>Jenis</span>
            <span>Lembaga</span>
            <span className="text-right">Plafon</span>
            <span className="text-right">Baki Debet</span>
            <span className="text-right">Angsuran</span>
            <span className="w-10 text-center">Kol</span>
          </div>

          {/* Loan rows */}
          {loans.map((l) => (
            <div
              key={`${l.jenis}-${l.lembaga}`}
              className="grid grid-cols-[1.1fr_1.1fr_1fr_1fr_1fr_auto] items-center gap-2 border-t border-bri-line/50 px-2 py-1 text-[9px]"
            >
              <span className="font-medium text-bri-ink">{l.jenis}</span>
              <span className="truncate text-bri-muted">{l.lembaga}</span>
              <span className="text-right tabular-nums text-bri-ink">{formatRupiah(l.plafon)}</span>
              <span className="text-right tabular-nums text-bri-ink">{formatRupiah(l.baki)}</span>
              <span className="text-right font-semibold tabular-nums text-bri-blue">
                {formatRupiah(l.angsuran)}
              </span>
              <span className="flex w-10 justify-center">
                <span
                  className={cn(
                    "rounded-pill px-1.5 py-px text-[7.5px] font-semibold",
                    l.kualitas === 1
                      ? "bg-emerald-50 text-emerald-600"
                      : "bg-amber-50 text-amber-600"
                  )}
                >
                  Kol {l.kualitas}
                </span>
              </span>
            </div>
          ))}

          {/* Total row */}
          <div className="grid grid-cols-[1.1fr_1.1fr_1fr_1fr_1fr_auto] items-center gap-2 border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[9px]">
            <span className="font-semibold text-bri-ink">Total</span>
            <span />
            <span />
            <span className="text-right text-[8px] text-bri-muted">Angsuran/bln</span>
            <span className="text-right font-bold tabular-nums text-bri-navy">
              {formatRupiah(totalAngsuran)}
            </span>
            <span />
          </div>
        </div>
      )}
    </div>
  );
}
