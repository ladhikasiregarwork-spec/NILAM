"use client";

import { useState } from "react";
import { ClipboardCheck, Home, Wallet, Coins, Gauge, CheckCircle2, XCircle, ChevronDown, Pencil, CalendarClock, Receipt } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import { penghasilanBulanan, dirRate, kemampuanBayar } from "@/lib/kemampuan";
import { maxPlafond } from "@/lib/kpr";
import type { NodeStatus } from "@/types/orchestration";

const KPR_RATE = 0.105; // indikatif untuk batas kemampuan

interface Breakdown {
  harga?: number;
  dpAwal: number;
  kebutuhan?: number;
  npw?: number;
  ltv: number;
  plafonAgunan?: number;
  tenorBulan: number;
  gajiBulanan: number;
  thrTahunan: number;
  bonusTahunan: number;
  slikAngsuran: number;
  factors: { label: string; points: number; max: number; detail: string }[];
}

interface SummaryDecisionCardProps {
  status: NodeStatus;
  kemampuan: number;
  angsuranKpr?: number;
  score: number;
  grade: string;
  breakdown: Breakdown;
}

type Decision = "none" | "approved" | "rejected";

function scoreColor(score: number): string {
  if (score >= 80) return "#16A34A";
  if (score >= 65) return "#0EA5E9";
  if (score >= 50) return "#F59E0B";
  return "#EF4444";
}

const pct = (r: number) => `${(r * 100).toFixed(2).replace(/\.?0+$/, "").replace(".", ",")}%`;

/** Key/value line inside an expanded detail panel. */
function DetailRow({ label, value, strong, accent }: { label: string; value: string; strong?: boolean; accent?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[8px] text-bri-muted">{label}</span>
      <span className={cn("tabular-nums", strong ? "text-[9px] font-bold" : "text-[8.5px] font-medium", accent ?? "text-bri-ink")}>{value}</span>
    </div>
  );
}

/**
 * SummaryDecisionCard — "Ringkasan & Keputusan". Empat metrik kunci yang bisa
 * di-expand (dropdown) untuk melihat rincian perhitungannya: Plafond Pembiayaan,
 * Total DP, Kemampuan Bayar, Credit Scoring. Lalu tombol keputusan analis.
 */
export function SummaryDecisionCard({ status, kemampuan: _kemampuan, angsuranKpr, score, grade, breakdown: b }: SummaryDecisionCardProps) {
  const ready = status === "success";
  const [decision, setDecision] = useState<Decision>("none");
  const [open, setOpen] = useState<string | null>(null);
  // Bonus tahunan editable (default = nilai terbaca OCR); null = belum diedit.
  const [bonusEdit, setBonusEdit] = useState<number | null>(null);
  const bonusEff = bonusEdit ?? b.bonusTahunan;
  const penghasilanEff = penghasilanBulanan(b.gajiBulanan, b.thrTahunan, bonusEff);
  const dirEff = dirRate(penghasilanEff);
  const kemampuanEff = kemampuanBayar(b.gajiBulanan, b.thrTahunan, bonusEff, b.slikAngsuran);

  // Plafond pembiayaan di-cap oleh kebutuhan, agunan (NPW×LTV), DAN kemampuan
  // bayar — jadi saat bonus/kemampuan diedit, plafond & total DP ikut berubah.
  const maxAfford = kemampuanEff > 0 ? maxPlafond(kemampuanEff, KPR_RATE, b.tenorBulan) : Infinity;
  const plafonRaw = Math.min(b.kebutuhan ?? Infinity, b.plafonAgunan ?? Infinity, maxAfford);
  const plafonPembiayaan = Number.isFinite(plafonRaw) ? Math.round(plafonRaw) : undefined;
  const totalDp = b.harga != null && plafonPembiayaan != null ? b.harga - plafonPembiayaan : undefined;
  const tambahanDp = totalDp != null ? Math.max(0, totalDp - b.dpAwal) : undefined;
  // Which cap is binding (for the detail note).
  const capLabel =
    plafonPembiayaan == null ? null
      : plafonPembiayaan === Math.round(maxAfford) && maxAfford !== Infinity ? "dibatasi kemampuan"
      : b.plafonAgunan != null && plafonPembiayaan === b.plafonAgunan ? "dibatasi agunan"
      : "sesuai kebutuhan";

  const color = scoreColor(score);
  const layak = angsuranKpr != null && kemampuanEff > 0 ? angsuranKpr <= kemampuanEff : undefined;
  const toggle = (id: string) => setOpen((o) => (o === id ? null : id));

  function Metric({ id, icon, label, value, valueNote, children }: {
    id: string; icon: React.ReactNode; label: string; value: string; valueNote?: React.ReactNode; children: React.ReactNode;
  }) {
    const isOpen = open === id;
    return (
      <div className={cn("rounded-lg border bg-bri-bg/40 transition-colors", isOpen ? "border-bri-blue/50" : "border-bri-line")}>
        <button type="button" onClick={() => toggle(id)} className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-left">
          <span className="flex items-center gap-1 text-[8.5px] text-bri-muted">{icon} {label}</span>
          <span className="flex items-center gap-1.5">
            <span className="text-right">
              <span className="block text-[12px] font-bold leading-none tabular-nums text-bri-navy">{value}</span>
              {valueNote}
            </span>
            <ChevronDown size={13} className={cn("shrink-0 text-bri-muted transition-transform", isOpen && "rotate-180")} />
          </span>
        </button>
        {isOpen && <div className="flex flex-col gap-0.5 border-t border-bri-line/70 px-2.5 py-1.5">{children}</div>}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-bri-line bg-white px-3 py-2.5 shadow-soft">
      <div className="mb-2 flex items-center gap-1">
        <ClipboardCheck size={11} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">Ringkasan &amp; Keputusan</span>
      </div>

      {!ready ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu pemrosesan…</span>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-1.5">
          {/* Plafond Pembiayaan */}
          <Metric
            id="plafond"
            icon={<Home size={10} />}
            label="Plafond Pembiayaan"
            value={plafonPembiayaan != null ? formatRupiah(plafonPembiayaan) : "—"}
            valueNote={capLabel && <span className="block text-[7px] font-medium text-bri-muted">{capLabel}</span>}
          >
            <DetailRow label="Harga Rumah" value={b.harga != null ? formatRupiah(b.harga) : "—"} />
            <DetailRow label="DP Awal" value={`− ${formatRupiah(b.dpAwal)}`} />
            <DetailRow label="Kebutuhan (Harga − DP)" value={b.kebutuhan != null ? formatRupiah(b.kebutuhan) : "—"} />
            <div className="my-0.5 border-t border-bri-line/60" />
            <DetailRow label="Plafon Agunan (NPW × LTV)" value={b.plafonAgunan != null ? formatRupiah(b.plafonAgunan) : "—"} />
            <DetailRow label={`Batas Kemampuan (× ${b.tenorBulan / 12} thn)`} value={Number.isFinite(maxAfford) ? formatRupiah(Math.round(maxAfford)) : "—"} accent={plafonPembiayaan === Math.round(maxAfford) ? "text-red-500" : "text-bri-ink"} />
            <div className="my-0.5 border-t border-bri-line/60" />
            <DetailRow label="Plafond = min(Kebutuhan, Agunan, Kemampuan)" value={plafonPembiayaan != null ? formatRupiah(plafonPembiayaan) : "—"} strong accent="text-bri-navy" />
          </Metric>

          {/* Total DP */}
          <Metric id="dp" icon={<Coins size={10} />} label="Total DP" value={totalDp != null ? formatRupiah(totalDp) : "—"}>
            <DetailRow label="DP Awal" value={formatRupiah(b.dpAwal)} />
            <DetailRow label="Tambahan DP (plafond < kebutuhan)" value={`+ ${formatRupiah(tambahanDp ?? 0)}`} accent={(tambahanDp ?? 0) > 0 ? "text-red-500" : "text-bri-ink"} />
            <div className="my-0.5 border-t border-bri-line/60" />
            <DetailRow label="Total DP = Harga − Plafond" value={totalDp != null ? formatRupiah(totalDp) : "—"} strong accent="text-bri-navy" />
          </Metric>

          {/* Kemampuan Bayar */}
          <Metric
            id="kemampuan"
            icon={<Wallet size={10} />}
            label="Kemampuan Bayar / bln"
            value={formatRupiah(kemampuanEff)}
            valueNote={layak != null && <span className={cn("block text-[7px] font-semibold", layak ? "text-emerald-600" : "text-red-500")}>{layak ? "angsuran KPR layak" : "angsuran KPR melebihi"}</span>}
          >
            <DetailRow label="Gaji / bulan" value={formatRupiah(b.gajiBulanan)} />
            <DetailRow label="THR / 12" value={`+ ${formatRupiah(Math.round(b.thrTahunan / 12))}`} />
            {/* Bonus — editable (default dari OCR) */}
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1 text-[8px] text-bri-muted">Bonus / 12 <Pencil size={7} className="text-bri-muted/60" /></span>
              <span className="flex items-center gap-1">
                <span className="text-[8px] text-bri-muted">+</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={bonusEff.toLocaleString("id-ID")}
                  onChange={(e) => setBonusEdit(Number(e.target.value.replace(/[^\d]/g, "")) || 0)}
                  title="Bonus tahunan (bisa diedit)"
                  className="w-[88px] rounded border border-bri-line bg-white px-1 py-0.5 text-right text-[8px] tabular-nums text-bri-ink focus:border-bri-blue focus:outline-none"
                />
                <span className="text-[7px] text-bri-muted">/12</span>
              </span>
            </div>
            <DetailRow label="Penghasilan / bln" value={formatRupiah(Math.round(penghasilanEff))} />
            <DetailRow label="Angsuran SLIK (aktif)" value={`− ${formatRupiah(b.slikAngsuran)}`} />
            <DetailRow label="× DIR (sesuai penghasilan)" value={pct(dirEff)} />
            {angsuranKpr != null && <DetailRow label="Estimasi angsuran KPR" value={formatRupiah(angsuranKpr)} accent={layak ? "text-emerald-600" : "text-red-500"} />}
            <div className="my-0.5 border-t border-bri-line/60" />
            <DetailRow label="Kemampuan Bayar / bln" value={formatRupiah(kemampuanEff)} strong accent="text-bri-navy" />
          </Metric>

          {/* Credit Scoring */}
          <Metric
            id="score"
            icon={<Gauge size={10} />}
            label="Credit Scoring"
            value={String(score)}
            valueNote={<span className="mt-0.5 inline-block rounded-pill px-1.5 py-px text-[7px] font-bold text-white" style={{ background: color }}>{grade}</span>}
          >
            {b.factors.map((f) => (
              <div key={f.label} className="flex items-center gap-1.5">
                <span className="w-[72px] shrink-0 truncate text-[7.5px] text-bri-ink" title={f.label}>{f.label}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bri-bg">
                  <div className="h-full rounded-full" style={{ width: `${(f.points / f.max) * 100}%`, background: color }} />
                </div>
                <span className="w-[54px] shrink-0 text-right text-[7px] text-bri-muted">{f.detail} · <span className="font-semibold text-bri-ink">{f.points}/{f.max}</span></span>
              </div>
            ))}
          </Metric>

          {/* Tenor + angsuran aktif */}
          <div className="flex gap-1.5">
            <div className="flex-1 rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
              <p className="flex items-center gap-1 text-[8px] text-bri-muted"><CalendarClock size={10} /> Tenor</p>
              <p className="text-[12px] font-bold tabular-nums text-bri-navy">{Math.round(b.tenorBulan / 12)} tahun</p>
            </div>
            <div className="flex-1 rounded-lg border border-bri-line bg-bri-bg/40 px-2.5 py-1.5">
              <p className="flex items-center gap-1 text-[8px] text-bri-muted"><Receipt size={10} /> Angsuran Aktif (SLIK) / bln</p>
              <p className="text-[12px] font-bold tabular-nums text-bri-navy">{formatRupiah(b.slikAngsuran)}</p>
            </div>
          </div>

          <div className="flex-1" />

          {/* Decision */}
          {decision === "none" ? (
            <div className="flex gap-2">
              <button type="button" onClick={() => setDecision("approved")} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 py-2 text-[10px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]">
                <CheckCircle2 size={13} /> Approve
              </button>
              <button type="button" onClick={() => setDecision("rejected")} className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-red-300 bg-red-50 py-2 text-[10px] font-semibold text-red-600 transition-all hover:bg-red-100 active:scale-[0.98]">
                <XCircle size={13} /> Reject
              </button>
            </div>
          ) : (
            <div className={cn("flex items-center justify-between gap-2 rounded-lg border px-3 py-2", decision === "approved" ? "border-emerald-200 bg-emerald-50/60" : "border-red-200 bg-red-50/60")}>
              <span className={cn("flex items-center gap-1.5 text-[11px] font-bold", decision === "approved" ? "text-emerald-700" : "text-red-600")}>
                {decision === "approved" ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                {decision === "approved" ? "Pengajuan Disetujui" : "Pengajuan Ditolak"}
              </span>
              <button type="button" onClick={() => setDecision("none")} className="text-[8px] font-semibold text-bri-muted hover:text-bri-blue">Ubah</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
