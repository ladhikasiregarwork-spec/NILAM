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
  /** Which section to render. */
  view?: "summary" | "detail" | "tunggakan";
}

const VIEW_TITLE: Record<NonNullable<SlikOjkCardProps["view"]>, string> = {
  summary: "SLIK OJK · Ringkasan",
  detail: "SLIK OJK · Detail Fasilitas",
  tunggakan: "SLIK OJK · Riwayat Tunggakan",
};

// Flexible (fr) columns so the table fills the full dashboard width; a min-width
// keeps it readable + horizontally scrollable on narrow screens.
const GRID = "grid grid-cols-[1.7fr_1.1fr_1.2fr_0.7fr_1fr_1.1fr_0.9fr_0.5fr] items-center gap-2";

/** "8.25" → "8,25%", 21 → "21%". */
const pct = (b?: number) =>
  b == null ? "—" : `${b.toFixed(2).replace(/\.?0+$/, "").replace(".", ",")}%`;

/** "20241003" → "10/24" (MM/YY). */
const ym = (s?: string) => (s && s.length >= 6 ? `${s.slice(4, 6)}/${s.slice(2, 4)}` : "—");

/** Colour for a kolektibilitas class (1 lancar … 5 macet). */
function kolColor(k: number): string {
  if (k <= 1) return "bg-emerald-400";
  if (k === 2) return "bg-amber-400";
  if (k === 3) return "bg-orange-500";
  return "bg-red-500";
}

/** DPD (hari tunggakan) bucket per kolektibilitas. */
const KOL_DPD: Record<number, string> = { 1: "0 hari", 2: "1–90 hari", 3: "91–120 hari", 4: "121–180 hari", 5: "> 180 hari" };

/**
 * Deterministic kolektibilitas history (default 24 months, matching SLIK data):
 * the most recent months ramp up to the present class, older months are lancar.
 * (The SLIK Excel carries only the latest kol, so the timeline is reconstructed.)
 */
function kolHistory(kol: number, months = 24): number[] {
  const bad = Math.max(0, kol - 1);
  return Array.from({ length: months }, (_, m) => (m >= months - bad ? Math.min(kol, 2 + (m - (months - bad))) : 1));
}

/**
 * SlikOjkCard — "SLIK OJK (every loan user ever have)". Per-facility table from
 * the parsed SLIK Excel: lembaga, plafon, baki, bunga (p.a.), tenor, computed
 * angsuran, active status, collectibility — plus the TOTAL monthly installment
 * of active facilities. Gated until the SLIK retrieval step succeeds.
 */
export function SlikOjkCard({ status, loans, totalAngsuran, score, view = "summary" }: SlikOjkCardProps) {
  const ready = status === "success";

  const activeLoans = loans.filter((l) => l.aktif !== false);
  const worstKol = loans.reduce((m, l) => Math.max(m, l.kualitas ?? 1), 1);
  const totalPlafon = loans.reduce((s, l) => s + (l.plafon ?? 0), 0);
  const totalBaki = loans.reduce((s, l) => s + (l.baki ?? 0), 0);
  const pernahMenunggak = loans.filter((l) => (l.kualitas ?? 1) > 1).length;
  const worst2 = [...loans].sort((a, b) => (b.kualitas ?? 1) - (a.kualitas ?? 1)).slice(0, 2);

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Landmark size={11} className="text-bri-navy" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
            {VIEW_TITLE[view]}
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
        <div className="flex flex-col gap-2">
          {view === "summary" ? (
            <div className="flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                <p className="text-[8px] text-bri-muted">Total Angsuran Aktif</p>
                <p className="text-[13px] font-bold tabular-nums text-bri-navy">{formatRupiah(totalAngsuran)}</p>
              </div>
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                <p className="text-[8px] text-bri-muted">Fasilitas (Aktif / Total)</p>
                <p className="text-[13px] font-bold tabular-nums text-bri-ink">{activeLoans.length} / {loans.length}</p>
              </div>
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                <p className="text-[8px] text-bri-muted">Plafon / Baki Debet</p>
                <p className="text-[10px] font-semibold tabular-nums text-bri-ink">{formatRupiah(totalPlafon)} <span className="text-bri-muted">/ {formatRupiah(totalBaki)}</span></p>
              </div>
              <div className="rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                <p className="text-[8px] text-bri-muted">Kolektibilitas Terburuk</p>
                <p className="flex items-center gap-1.5">
                  <span className={cn("rounded-pill px-1.5 py-px text-[9px] font-bold", worstKol === 1 ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600")}>Kol {worstKol}</span>
                  <span className="text-[8px] text-bri-muted">Score {score}</span>
                </p>
              </div>
            </div>

            {/* Riwayat tunggakan — 2 fasilitas terburuk */}
            <div className="rounded-lg border border-bri-line bg-white px-2.5 py-2">
              <p className="mb-1.5 flex items-center justify-between text-[8px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
                <span>Riwayat Tunggakan · 2 Terburuk</span>
                <span className="font-medium normal-case text-bri-muted/70">12 bln terakhir</span>
              </p>
              <div className="flex flex-col gap-1.5">
                {worst2.map((l, i) => {
                  const k = l.kualitas ?? 1;
                  const hist = kolHistory(k, 12);
                  return (
                    <div key={`${l.lembaga}-${i}`} className="flex items-center gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[8.5px] font-medium text-bri-ink" title={l.lembaga}>{l.lembaga}</p>
                        <p className="text-[7px] text-bri-muted">Kol {k} · {KOL_DPD[k] ?? "—"}</p>
                      </div>
                      <div className="flex shrink-0 gap-0.5">
                        {hist.map((kk, m) => (
                          <span key={m} className={cn("h-3 w-1.5 rounded-[1px]", kolColor(kk))} title={`Kol ${kk} · ${KOL_DPD[kk]}`} />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            </div>
          ) : view === "detail" ? (
        <div className="overflow-x-auto scroll-thin">
        <div className="w-full min-w-[640px] overflow-hidden rounded-lg border border-bri-line/70">
          <div className={cn(GRID, "bg-bri-bg/70 px-2 py-1 text-[7px] font-semibold uppercase tracking-[0.04em] text-bri-muted")}>
            <span>Lembaga / Jenis</span>
            <span className="text-right">Plafon</span>
            <span className="text-right">Baki Debet</span>
            <span className="text-right">Bunga</span>
            <span className="text-center">Tenor</span>
            <span className="text-right">Angsuran</span>
            <span className="text-center">Status</span>
            <span className="text-center">Kol</span>
          </div>

          {loans.map((l, i) => (
            <div key={`${l.lembaga}-${i}`} className={cn(GRID, "border-t border-bri-line/50 px-2 py-1 text-[8.5px]")}>
              <span className="flex min-w-0 flex-col">
                <span className="truncate font-medium text-bri-ink" title={l.lembaga}>{l.lembaga}</span>
                <span className="truncate text-[7px] text-bri-muted" title={l.jenis}>{l.jenis}</span>
              </span>
              <span className="text-right tabular-nums text-bri-ink">{formatRupiah(l.plafon)}</span>
              <span className="text-right tabular-nums text-bri-ink">{formatRupiah(l.baki)}</span>
              <span className="text-right tabular-nums text-bri-ink">{pct(l.sukuBunga)}</span>
              <span className="text-center text-[7.5px] tabular-nums text-bri-muted">
                {ym(l.tanggalMulai)}–{ym(l.tanggalJatuhTempo)}
              </span>
              <span className={cn("text-right font-semibold tabular-nums", l.aktif === false ? "text-bri-muted/60" : "text-bri-blue")}>
                {formatRupiah(l.angsuran)}
              </span>
              <span className="flex justify-center">
                <span className={cn("rounded-pill px-1.5 py-px text-[7px] font-semibold", l.aktif === false ? "bg-bri-bg text-bri-muted" : "bg-emerald-50 text-emerald-600")}>
                  {l.aktif === false ? "Non-aktif" : "Aktif"}
                </span>
              </span>
              <span className="flex justify-center">
                <span className={cn("rounded-pill px-1.5 py-px text-[7.5px] font-semibold", l.kualitas === 1 ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600")}>
                  {l.kualitas}
                </span>
              </span>
            </div>
          ))}

          <div className={cn(GRID, "border-t border-bri-line bg-bri-bg/40 px-2 py-1 text-[8.5px]")}>
            <span className="font-semibold text-bri-ink">Total Angsuran (Aktif)</span>
            <span />
            <span />
            <span />
            <span />
            <span className="text-right font-bold tabular-nums text-bri-navy">{formatRupiah(totalAngsuran)}</span>
            <span />
            <span />
          </div>
        </div>
        </div>
          ) : (
            /* Riwayat Tunggakan — 24-bulan kolektibilitas per fasilitas */
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2 rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
                <span className="text-[8.5px] text-bri-muted">Pernah Menunggak (kol &gt; 1) · 24 bln terakhir</span>
                <span className="text-[10px] font-bold text-bri-ink">
                  {pernahMenunggak} / {loans.length} fasilitas
                  <span className="ml-1.5 font-medium text-bri-muted">· tunggakan terburuk {KOL_DPD[worstKol] ?? "—"}</span>
                </span>
              </div>

              <div className="overflow-x-auto scroll-thin">
                <div className="w-full min-w-[820px]">
                  <div className="grid grid-cols-[1.4fr_repeat(24,1fr)] items-center gap-0.5 px-1 pb-0.5 text-[6px] font-semibold uppercase text-bri-muted">
                    <span>Fasilitas</span>
                    {Array.from({ length: 24 }, (_, i) => <span key={i} className="text-center">{i === 0 ? "24bln" : i === 23 ? "kini" : ""}</span>)}
                  </div>
                  {loans.map((l, i) => {
                    const hist = kolHistory(l.kualitas ?? 1, 24);
                    return (
                      <div key={`${l.lembaga}-${i}`} className="grid grid-cols-[1.4fr_repeat(24,1fr)] items-center gap-0.5 border-t border-bri-line/40 px-1 py-1">
                        <span className="min-w-0 truncate text-[7.5px] text-bri-ink" title={l.lembaga}>{l.lembaga}</span>
                        {hist.map((k, m) => (
                          <span key={m} className="flex justify-center">
                            <span className={cn("h-2.5 w-full max-w-[14px] rounded-[2px]", kolColor(k))} title={`Bln ${m + 1} · Kol ${k} · ${KOL_DPD[k]}`} />
                          </span>
                        ))}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[7px] text-bri-muted">
                {([[1, "Lancar"], [2, "DPK"], [3, "Kurang Lancar"], [4, "Diragukan"], [5, "Macet"]] as [number, string][]).map(([k, label]) => (
                  <span key={k} className="flex items-center gap-1">
                    <span className={cn("h-2 w-2 rounded-[2px]", kolColor(k))} /> Kol {k} {label}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
