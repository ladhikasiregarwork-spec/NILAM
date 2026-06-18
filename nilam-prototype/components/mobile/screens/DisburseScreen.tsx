"use client";

import { useState } from "react";
import { CheckCircle2, RefreshCw, Wallet, MapPin, CalendarRange, AlertTriangle } from "lucide-react";
import { formatRupiah } from "@/lib/formatRupiah";
import type { AgunanData } from "@/types/agunan";

interface DisburseScreenProps {
  agunan?: AgunanData;
  /** Down payment (uang muka). */
  uangMuka?: number;
  /** Collateral plafond cap = NPW × LTV (limits the financed amount). */
  plafonAgunan?: number;
  onFinish: () => void;
}

function Row({ label, value, strong, className }: { label: string; value: string; strong?: boolean; className?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[9px] text-bri-muted">{label}</span>
      <span className={`tabular-nums ${strong ? "text-[12px] font-bold" : "text-[10px] font-medium"} ${className ?? "text-bri-ink"}`}>{value}</span>
    </div>
  );
}

/**
 * DisburseScreen — langkah akhir. Dana dibiayai = plafon yang ditawarkan
 * (dibatasi NPW × LTV). Diarahkan ke AKAD di kantor cabang pada tanggal akad;
 * rincian DP yang harus dibayar saat akad (termasuk tambahan DP) + dana yang
 * dibiayai.
 */
export function DisburseScreen({ agunan, uangMuka, plafonAgunan, onFinish }: DisburseScreenProps) {
  const harga = agunan?.harga ?? 0;
  const dp = uangMuka ?? 0;
  const capColl = plafonAgunan != null && plafonAgunan > 0 ? plafonAgunan : Infinity;
  const danaDibiayai = Math.max(0, Math.min(harga - dp, capColl));
  const dpSaatAkad = harga > 0 ? Math.max(0, harga - danaDibiayai) : dp; // = dp + tambahan
  const tambahanDp = Math.max(0, dpSaatAkad - dp);

  const kantorCabang = agunan?.kota ? `BRI Kantor Cabang ${agunan.kota}` : "BRI Kantor Cabang Terdekat";
  // Akad dijadwalkan ~7 hari ke depan (dihitung sekali saat layar muncul).
  const [tglAkad] = useState(() =>
    new Date(Date.now() + 7 * 86_400_000).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" }),
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-4 py-3">
      <div className="flex flex-col items-center gap-1.5">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100">
          <CheckCircle2 size={28} className="text-emerald-500" strokeWidth={1.8} />
        </div>
        <p className="text-sm font-bold text-bri-ink">Pengajuan Disetujui</p>
        <p className="text-center text-[10px] leading-relaxed text-bri-muted">
          Penawaran diterima. Lanjut ke <b>akad kredit</b> di kantor cabang.
        </p>
      </div>

      {/* Dana dibiayai */}
      <div className="mt-3 flex w-full items-center gap-2 rounded-bubble border border-emerald-200 bg-emerald-50 px-4 py-2.5">
        <Wallet size={18} className="shrink-0 text-emerald-600" />
        <div className="min-w-0 flex-1">
          <p className="text-[8px] text-bri-muted">Dana Dibiayai (dicairkan)</p>
          <p className="text-[16px] font-bold text-emerald-700 tabular-nums">{formatRupiah(danaDibiayai)}</p>
        </div>
      </div>

      {/* Rincian biaya */}
      {harga > 0 && (
        <div className="mt-2 flex flex-col gap-1 rounded-bubble border border-bri-line bg-white px-3 py-2 shadow-soft">
          <Row label="Harga Properti" value={formatRupiah(harga)} />
          <Row label="Uang Muka (awal)" value={formatRupiah(dp)} />
          {tambahanDp > 0 && <Row label="Tambahan DP (plafon dibatasi agunan)" value={`+ ${formatRupiah(tambahanDp)}`} className="text-red-500" />}
          <div className="my-0.5 border-t border-bri-line" />
          <Row label="DP dibayar saat akad" value={formatRupiah(dpSaatAkad)} strong className="text-bri-navy" />
          <Row label="Dana dibiayai (KPR)" value={formatRupiah(danaDibiayai)} strong className="text-emerald-700" />
          {tambahanDp > 0 && (
            <p className="mt-0.5 flex items-start gap-1 text-[7.5px] text-amber-600">
              <AlertTriangle size={9} className="mt-0.5 shrink-0" />
              Plafon dibiayai dibatasi NPW × LTV → DP bertambah {formatRupiah(tambahanDp)}, dibayar saat akad.
            </p>
          )}
        </div>
      )}

      {/* Akad */}
      <div className="mt-2 rounded-bubble border border-bri-blue/30 bg-bri-blue/5 px-3 py-2">
        <p className="mb-1 text-[8px] font-semibold uppercase tracking-[0.1em] text-bri-blue">Jadwal Akad Kredit</p>
        <div className="flex items-start gap-1.5">
          <MapPin size={12} className="mt-0.5 shrink-0 text-bri-blue" />
          <div className="min-w-0">
            <p className="text-[8px] text-bri-muted">Lokasi Akad</p>
            <p className="text-[10px] font-semibold text-bri-ink">{kantorCabang}</p>
            {agunan?.kelurahan && (
              <p className="truncate text-[7.5px] text-bri-muted">
                {[agunan.kecamatan, agunan.kota, agunan.provinsi].filter(Boolean).join(", ")}
              </p>
            )}
          </div>
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 border-t border-bri-blue/20 pt-1.5">
          <CalendarRange size={12} className="shrink-0 text-bri-blue" />
          <div>
            <span className="text-[8px] text-bri-muted">Tanggal Akad </span>
            <span className="text-[10px] font-semibold text-bri-ink">{tglAkad}</span>
          </div>
        </div>
      </div>

      {/* Nomor pencairan */}
      <div className="mt-2 rounded-bubble border border-bri-line bg-bri-bg px-3 py-1.5 text-center">
        <span className="text-[8px] text-bri-muted">Nomor Pengajuan </span>
        <span className="font-mono text-[10px] font-semibold text-bri-blue">KPR-2026-0000123</span>
      </div>

      <div className="flex-1" />

      <button
        type="button"
        onClick={onFinish}
        className="mt-3 flex items-center justify-center gap-1.5 self-center text-[10px] text-bri-muted transition-colors hover:text-bri-blue"
      >
        <RefreshCw size={11} />
        Selesai · mulai aplikasi baru
      </button>
    </div>
  );
}
