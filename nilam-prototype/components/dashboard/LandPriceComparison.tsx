"use client";

import { MapPinned, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import type { AgunanData } from "@/types/agunan";

interface LandPriceComparisonProps {
  agunan?: AgunanData;
  /** Land-value portion of the NPW (preferred). */
  npwLand?: number;
  /** Full NPW (fallback to estimate land/m² when npwLand is absent). */
  npw?: number;
  /** Tighter layout for the narrow RM phone. */
  compact?: boolean;
}

/** Deterministic nearby comparables (no real comps API) — factors around NPW. */
const COMPS: { suffix: string; f: number; ltF: number }[] = [
  { suffix: "jalan utama", f: 1.16, ltF: 0.9 },
  { suffix: "sisi utara", f: 1.06, ltF: 1.0 },
  { suffix: "sisi selatan", f: 0.94, ltF: 1.1 },
  { suffix: "gang dalam", f: 0.84, ltF: 0.8 },
];

/**
 * LandPriceComparison — "Survey Harga Tanah Sekitar". Membandingkan harga tanah
 * di sekitar agunan dengan harga tanah versi NPW (Nilai Pasar Wajar). Harga/m²
 * NPW dari land_value model; pembanding di-generate di sekitar nilai itu untuk
 * validasi taksiran. (Data pembanding sintetis untuk demo.)
 */
export function LandPriceComparison({ agunan, npwLand, npw, compact }: LandPriceComparisonProps) {
  const lt = agunan?.luasTanah;
  // Land price per m²: prefer NPW land value; else estimate ~60% of NPW is land.
  const landPerM2 =
    npwLand != null && lt ? Math.round(npwLand / lt) : npw != null && lt ? Math.round((npw * 0.6) / lt) : undefined;

  const baseArea = agunan?.kelurahan || agunan?.kecamatan || agunan?.kota || "sekitar agunan";

  if (landPerM2 == null) {
    return (
      <div className="rounded-xl border border-bri-line bg-bri-bg/40 px-3 py-2">
        <p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.1em] text-bri-muted"><MapPinned size={11} /> Survey Harga Tanah Sekitar</p>
        <p className="mt-1 text-[8.5px] italic text-bri-muted/60">Perlu luas tanah & NPW untuk membandingkan harga tanah.</p>
      </div>
    );
  }

  const comps = COMPS.map((c) => ({
    label: `${baseArea} · ${c.suffix}`,
    perM2: Math.round(landPerM2 * c.f),
    lt: lt ? Math.round(lt * c.ltF) : undefined,
    delta: (c.f - 1) * 100,
  }));
  const avg = Math.round(comps.reduce((s, c) => s + c.perM2, 0) / comps.length);
  const avgDelta = ((avg - landPerM2) / landPerM2) * 100;

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.1em] text-bri-muted"><MapPinned size={11} className="text-bri-navy" /> Survey Harga Tanah Sekitar</p>
        <span className="rounded-pill bg-bri-bg px-2 py-0.5 text-[7.5px] font-semibold text-bri-navy">vs NPW</span>
      </div>

      {/* NPW baseline */}
      <div className="mb-1.5 flex items-center justify-between gap-2 rounded-lg border border-bri-blue/30 bg-bri-blue/5 px-2.5 py-1.5">
        <span className="text-[8.5px] font-medium text-bri-ink">Harga Tanah NPW (model)</span>
        <span className="text-[12px] font-bold tabular-nums text-bri-navy">{formatRupiah(landPerM2)}<span className="text-[8px] font-normal text-bri-muted">/m²</span></span>
      </div>

      {/* Comparables */}
      <div className="overflow-hidden rounded-lg border border-bri-line/70">
        <div className={cn("grid items-center gap-1 bg-bri-bg/70 px-2 py-1 text-[6.5px] font-semibold uppercase tracking-[0.03em] text-bri-muted", compact ? "grid-cols-[1fr_58px_44px]" : "grid-cols-[1.6fr_60px_70px_48px]")}>
          <span>Lokasi Pembanding</span>
          {!compact && <span className="text-right">LT</span>}
          <span className="text-right">Harga/m²</span>
          <span className="text-right">vs NPW</span>
        </div>
        {comps.map((c, i) => (
          <div key={i} className={cn("grid items-center gap-1 border-t border-bri-line/50 px-2 py-1 text-[8px]", compact ? "grid-cols-[1fr_58px_44px]" : "grid-cols-[1.6fr_60px_70px_48px]")}>
            <span className="min-w-0 truncate text-bri-ink" title={c.label}>{c.label}</span>
            {!compact && <span className="text-right tabular-nums text-bri-muted">{c.lt ?? "—"} m²</span>}
            <span className="text-right tabular-nums text-bri-ink">{formatRupiah(c.perM2)}</span>
            <span className={cn("flex items-center justify-end gap-0.5 text-right font-semibold tabular-nums", c.delta >= 0 ? "text-emerald-600" : "text-red-500")}>
              {c.delta >= 0 ? <TrendingUp size={8} /> : <TrendingDown size={8} />}{c.delta >= 0 ? "+" : ""}{c.delta.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      <p className="mt-1 text-[7.5px] text-bri-muted">
        Rata-rata pembanding <b className="text-bri-ink">{formatRupiah(avg)}/m²</b> ({avgDelta >= 0 ? "+" : ""}{avgDelta.toFixed(0)}% vs NPW) — NPW {avgDelta >= 0 ? "konservatif" : "di atas pasar sekitar"}.
        <span className="text-bri-muted/60"> Data pembanding indikatif.</span>
      </p>
    </div>
  );
}
