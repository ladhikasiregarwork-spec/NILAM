"use client";

import { Loader2, ClipboardCheck, MapPin, Clock, XCircle, PencilLine } from "lucide-react";
import { formatRupiah } from "@/lib/formatRupiah";
import type { AgunanData } from "@/types/agunan";
import type { SurveyStatus } from "@/types/flow";

interface SurveyScreenProps {
  status: SurveyStatus;
  agunan?: AgunanData;
  /** RM survey note (shown on rejection). */
  note?: string;
  /** RM appraised value (shown on rejection context). */
  surveyValue?: number;
  /** Go back to the agunan step to swap the collateral and re-apply. */
  onEditAgunan: () => void;
}

/**
 * SurveyScreen — shown for collateral ≥ Rp500 juta. After processing, the
 * application waits in the Relationship Manager (RM) survey queue:
 *   pending  → "menunggu survey RM" (waiting)
 *   rejected → survey result rejected, with the RM note + "Ganti Agunan"
 * On approval the flow navigates straight to the offer, so this screen only
 * renders the pending / rejected states.
 */
export function SurveyScreen({ status, agunan, note, surveyValue, onEditAgunan }: SurveyScreenProps) {
  const lokasi = agunan
    ? [agunan.kelurahan, agunan.kecamatan, agunan.kota, agunan.provinsi].filter(Boolean).join(", ")
    : "";

  // ── Rejected ───────────────────────────────────────────────────────────────
  if (status === "rejected") {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center gap-3 px-5 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-50">
          <XCircle size={30} className="text-red-500" strokeWidth={2} />
        </div>
        <div>
          <p className="text-[13px] font-bold text-bri-ink">Hasil Survey: Belum Memenuhi Syarat</p>
          <p className="mt-1 text-[10px] leading-relaxed text-bri-muted">
            Mohon maaf, agunan Anda belum dapat disetujui berdasarkan hasil survey Relationship Manager.
          </p>
        </div>
        {note && (
          <div className="w-full rounded-xl border border-red-200 bg-red-50/60 px-3 py-2 text-left">
            <p className="text-[8px] font-semibold uppercase tracking-[0.1em] text-red-500">Catatan Surveyor</p>
            <p className="mt-0.5 text-[9.5px] leading-relaxed text-red-700">{note}</p>
            {surveyValue != null && (
              <p className="mt-1 text-[9px] text-red-600">
                Nilai taksiran survey: <b>{formatRupiah(surveyValue)}</b>
              </p>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={onEditAgunan}
          className="mt-1 flex items-center justify-center gap-1.5 rounded-bubble bg-bri-blue px-4 py-2 text-[11px] font-semibold text-white transition-all hover:opacity-90 active:scale-[0.98]"
        >
          <PencilLine size={13} /> Ganti Agunan
        </button>
      </div>
    );
  }

  // ── Pending (waiting in the RM survey queue) ────────────────────────────────
  return (
    <div className="flex h-full min-h-0 flex-col items-center justify-center gap-4 px-5">
      <div className="relative flex h-16 w-16 items-center justify-center">
        <Loader2 size={64} className="absolute animate-spin text-bri-blue/30" strokeWidth={1.5} />
        <ClipboardCheck size={28} className="text-bri-blue" strokeWidth={2} />
      </div>

      <div className="text-center">
        <p className="text-[13px] font-bold text-bri-ink">Menunggu Survey Agunan</p>
        <p className="mx-auto mt-1 max-w-[240px] text-[10px] leading-relaxed text-bri-muted">
          Karena nilai agunan ≥ Rp500 juta, agunan Anda akan disurvey oleh Relationship Manager kami sebelum penawaran
          diterbitkan.
        </p>
      </div>

      {/* Collateral summary */}
      {agunan?.harga != null && (
        <div className="w-full rounded-xl border border-bri-line bg-bri-bg/50 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[9px] text-bri-muted">Nilai Agunan Diajukan</span>
            <span className="text-[12px] font-bold text-bri-navy tabular-nums">{formatRupiah(agunan.harga)}</span>
          </div>
          {(agunan.luasBangunan || agunan.luasTanah) && (
            <p className="mt-0.5 text-[8.5px] text-bri-muted">
              LB {agunan.luasBangunan ?? "—"} m² · LT {agunan.luasTanah ?? "—"} m²
            </p>
          )}
          {lokasi && (
            <div className="mt-1 flex items-start gap-1 border-t border-bri-line pt-1">
              <MapPin size={9} className="mt-0.5 shrink-0 text-bri-muted" />
              <span className="text-[8.5px] text-bri-ink">{lokasi}</span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-1.5 rounded-pill bg-amber-50 px-3 py-1 text-[9px] font-semibold text-amber-700">
        <Clock size={11} /> Survey dijadwalkan — mohon menunggu
      </div>

      <button
        type="button"
        onClick={onEditAgunan}
        className="mt-1 flex items-center gap-1.5 text-[10px] font-semibold text-bri-blue transition-colors hover:underline"
      >
        <PencilLine size={12} /> Ganti Agunan
      </button>
    </div>
  );
}
