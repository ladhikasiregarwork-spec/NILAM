"use client";

import { Gauge } from "lucide-react";
import { cn } from "@/lib/cn";
import type { CreditScoreResult } from "@/engines/scoring/creditScore";
import type { NodeStatus } from "@/types/orchestration";

interface CreditScoringCardProps {
  status: NodeStatus;
  result: CreditScoreResult;
}

function scoreColor(score: number): string {
  if (score >= 80) return "#16A34A";
  if (score >= 65) return "#0EA5E9";
  if (score >= 50) return "#F59E0B";
  return "#EF4444";
}

/**
 * CreditScoringCard — "CREDIT SCORING". 0–100 from 9 factors (pendidikan,
 * status kawin, usia, simpanan BRI, jangka waktu, % uang muka, tanggungan,
 * rasio gaji/angsuran, rasio harga/plafond). Score dial + per-factor bars.
 */
export function CreditScoringCard({ status, result }: CreditScoringCardProps) {
  const ready = status === "success";
  const { score, grade, factors } = result;
  const color = scoreColor(score);

  return (
    <div className="flex h-full flex-col rounded-xl border border-bri-line bg-white px-3 py-2.5 shadow-soft">
      <div className="mb-2 flex items-center gap-1">
        <Gauge size={11} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">Credit Scoring</span>
      </div>

      {!ready ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu pemrosesan…</span>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-2">
          {/* Score dial */}
          <div className="flex items-center gap-3">
            <div
              className="flex h-[60px] w-[60px] shrink-0 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(${color} ${score * 3.6}deg, #E5E9F0 0deg)` }}
            >
              <div className="flex h-[48px] w-[48px] flex-col items-center justify-center rounded-full bg-white">
                <span className="text-[18px] font-bold leading-none tabular-nums" style={{ color }}>{score}</span>
                <span className="text-[6px] text-bri-muted">/ 100</span>
              </div>
            </div>
            <div className="min-w-0">
              <span className="rounded-pill px-2 py-0.5 text-[9px] font-bold text-white" style={{ background: color }}>{grade}</span>
              <p className="mt-1 text-[7.5px] text-bri-muted">9 faktor: profil, agunan & rasio kemampuan</p>
            </div>
          </div>

          {/* Factor bars */}
          <div className="grid grid-cols-1 gap-[3px]">
            {factors.map((f) => (
              <div key={f.label} className="flex items-center gap-1.5">
                <span className="w-[78px] shrink-0 truncate text-[7.5px] text-bri-ink" title={f.label}>{f.label}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bri-bg">
                  <div className="h-full rounded-full" style={{ width: `${(f.points / f.max) * 100}%`, background: color }} />
                </div>
                <span className="w-[58px] shrink-0 text-right text-[7px] text-bri-muted">
                  {f.detail} · <span className="font-semibold text-bri-ink">{f.points}/{f.max}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
