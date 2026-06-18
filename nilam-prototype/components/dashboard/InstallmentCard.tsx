"use client";

import { useState } from "react";
import { Calculator, CheckCircle2, AlertTriangle, Pencil } from "lucide-react";
import { formatRupiah } from "@/lib/formatRupiah";
import { anuitas } from "@/lib/kpr";
import { kemampuanBayar, penghasilanBulanan, dirRate } from "@/lib/kemampuan";
import type { NodeStatus } from "@/types/orchestration";
import type { AgunanData } from "@/types/agunan";

interface InstallmentCardProps {
  status: NodeStatus;
  /** Monthly salary (gaji/bulan). */
  gajiBulanan: number;
  /** Annual THR. */
  thrTahunan: number;
  /** Annual bonus (default — editable here). */
  bonusTahunan: number;
  /** Existing total monthly installment from SLIK (active). */
  slikAngsuran: number;
  agunan?: AgunanData;
  /** Down payment (uang muka). */
  uangMuka?: number;
  /** Desired tenor in years. */
  jangkaWaktu?: number;
}

const KPR_RATE = 0.105; // indikatif

function Row({ label, value, strong, className }: { label: string; value: string; strong?: boolean; className?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[9px] text-white/70">{label}</span>
      <span className={`tabular-nums ${strong ? "text-[11px] font-bold text-white" : "text-[10px] font-medium text-white/90"} ${className ?? ""}`}>
        {value}
      </span>
    </div>
  );
}

/**
 * InstallmentCard — "Calculate Installment Payments".
 * Kemampuan bayar = gaji/bln + THR/12 + bonus/12 − angsuran SLIK (bonus dapat
 * diedit). Lalu estimasi angsuran KPR (plafon = harga − uang muka, tenor sesuai
 * input) dibandingkan dengan kemampuan → layak / tidak.
 */
export function InstallmentCard({
  status, gajiBulanan, thrTahunan, bonusTahunan, slikAngsuran, agunan, uangMuka, jangkaWaktu,
}: InstallmentCardProps) {
  const ready = status === "success";
  // Default = OCR-read annual bonus; null means "not yet edited" so it tracks
  // the OCR value even if it loads after mount.
  const [bonusEdit, setBonusEdit] = useState<number | null>(null);
  const bonus = bonusEdit ?? bonusTahunan;

  const penghasilan = penghasilanBulanan(gajiBulanan, thrTahunan, bonus);
  const dir = dirRate(penghasilan);
  const kemampuan = kemampuanBayar(gajiBulanan, thrTahunan, bonus, slikAngsuran);

  const harga = agunan?.harga;
  const plafond = harga != null ? Math.max(0, harga - (uangMuka ?? 0)) : undefined;
  const tenor = jangkaWaktu ?? 15;
  const kprAngsuran = plafond ? anuitas(plafond, KPR_RATE, tenor * 12) : undefined;
  const layak = kprAngsuran != null ? kprAngsuran <= kemampuan : undefined;

  return (
    <div
      className="rounded-xl border border-bri-navy/30 px-3 py-2.5 shadow-soft"
      style={{ background: "linear-gradient(135deg, #00305C 0%, #00529C 100%)" }}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Calculator size={11} className="text-white" strokeWidth={2} />
          <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-white/80">
            Perhitungan Kemampuan Bayar
          </span>
        </div>
        <span className="rounded-pill bg-white/15 px-2 py-0.5 text-[7.5px] font-semibold text-white/90">Kemampuan Bayar</span>
      </div>

      {!ready ? (
        <div className="flex h-12 items-center justify-center">
          <span className="text-[10px] italic text-white/50">Menunggu perhitungan…</span>
        </div>
      ) : (
        <div className="flex items-stretch gap-3">
          {/* Kemampuan hero */}
          <div className="flex w-[210px] shrink-0 flex-col justify-center rounded-lg bg-white/10 px-3 py-2">
            <span className="text-[9px] text-white/70">Kemampuan Bayar / bln</span>
            <span className="text-[22px] font-bold leading-tight text-white tabular-nums">{formatRupiah(kemampuan)}</span>
            <span className="text-[8px] text-white/60">(gaji + THR/12 + bonus/12 − SLIK) × DIR {Math.round(dir * 100)}%</span>
            {kprAngsuran != null && (
              <span className={`mt-1 inline-flex w-fit items-center gap-1 rounded-pill px-1.5 py-0.5 text-[8px] font-semibold ${layak ? "bg-emerald-400/20 text-emerald-200" : "bg-red-400/20 text-red-200"}`}>
                {layak ? <CheckCircle2 size={9} /> : <AlertTriangle size={9} />}
                {layak ? "KPR layak" : "KPR melebihi kemampuan"}
              </span>
            )}
          </div>

          {/* Breakdown */}
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
            <Row label="Gaji / bulan" value={formatRupiah(gajiBulanan)} />
            <Row label="THR / 12" value={`+ ${formatRupiah(Math.round(thrTahunan / 12))}`} />
            {/* Bonus — editable */}
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1 text-[9px] text-white/70">
                Bonus / 12 <Pencil size={8} className="text-white/50" />
              </span>
              <span className="flex items-center gap-1">
                <span className="text-[10px] text-white/90">+</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={bonus.toLocaleString("id-ID")}
                  onChange={(e) => setBonusEdit(Number(e.target.value.replace(/[^\d]/g, "")) || 0)}
                  title="Bonus tahunan (bisa diedit)"
                  className="w-[96px] rounded border border-white/30 bg-white/10 px-1.5 py-0.5 text-right text-[9px] font-medium text-white tabular-nums focus:border-white focus:outline-none"
                />
                <span className="text-[8px] text-white/50">/12</span>
              </span>
            </div>
            <div className="my-0.5 border-t border-white/20" />
            <Row label="Penghasilan / bln" value={formatRupiah(Math.round(penghasilan))} />
            <Row label="Angsuran SLIK (aktif)" value={`− ${formatRupiah(slikAngsuran)}`} />
            <Row label="× DIR (sesuai penghasilan)" value={`${Math.round(dir * 100)}%`} />
            <div className="my-0.5 border-t border-white/20" />
            <Row label="Kemampuan Bayar" value={formatRupiah(kemampuan)} strong />
            {kprAngsuran != null && (
              <Row label={`Angsuran KPR (${tenor} thn · plafon ${formatRupiah(plafond!)})`} value={formatRupiah(kprAngsuran)} className={layak ? "text-emerald-200" : "text-red-200"} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
