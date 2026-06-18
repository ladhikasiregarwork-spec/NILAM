"use client";

import { useState } from "react";
import { ScrollText, Check } from "lucide-react";
import { cn } from "@/lib/cn";

interface TermConditionScreenProps {
  onAccept: () => void;
}

const TERMS = [
  "Data & dokumen yang diberikan benar dan dapat dipertanggungjawabkan.",
  "Menyetujui pengecekan data biro kredit (SLIK OJK) oleh BRI.",
  "Memahami skema bunga KPR (fixed/berjenjang lalu floating) dan biaya yang berlaku.",
  "Agunan yang diajukan bebas sengketa dan sesuai data yang diisi.",
  "Pengajuan tidak mengikat hingga proses verifikasi & penilaian selesai.",
];

/**
 * TermConditionScreen — langkah pertama: Submit Term & Condition.
 * Centang persetujuan → lanjut ke upload dokumen.
 */
export function TermConditionScreen({ onAccept }: TermConditionScreenProps) {
  const [agree, setAgree] = useState(false);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-3 py-2">
      <div className="mb-2 flex items-center gap-1.5">
        <ScrollText size={14} className="text-bri-navy" />
        <h2 className="text-[13px] font-bold text-bri-ink">Syarat &amp; Ketentuan</h2>
      </div>
      <p className="mb-2 text-[9px] text-bri-muted">Baca &amp; setujui sebelum melanjutkan pengajuan KPR.</p>

      <div className="flex flex-col gap-1.5 rounded-xl border border-bri-line bg-bri-bg/40 p-2.5">
        {TERMS.map((t, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <span className="mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-bri-navy/10 text-[7px] font-bold text-bri-navy">
              {i + 1}
            </span>
            <span className="text-[9px] leading-relaxed text-bri-ink">{t}</span>
          </div>
        ))}
      </div>

      {/* Checkbox */}
      <button
        type="button"
        onClick={() => setAgree((v) => !v)}
        className="mt-3 flex items-center gap-2 text-left"
      >
        <span
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
            agree ? "border-bri-navy bg-bri-navy text-white" : "border-bri-line bg-white"
          )}
        >
          {agree && <Check size={11} strokeWidth={3} />}
        </span>
        <span className="text-[10px] font-medium text-bri-ink">
          Saya membaca &amp; menyetujui syarat &amp; ketentuan di atas.
        </span>
      </button>

      <div className="flex-1" />

      <button
        type="button"
        onClick={agree ? onAccept : undefined}
        disabled={!agree}
        className={cn(
          "mt-3 w-full rounded-bubble py-2.5 text-[12px] font-semibold text-white transition-all",
          agree ? "hover:opacity-90 active:scale-[0.98]" : "cursor-not-allowed opacity-60"
        )}
        style={{ background: agree ? "linear-gradient(135deg, #00529C 0%, #1A6FC4 100%)" : "#94A3B8" }}
      >
        Setuju &amp; Lanjut
      </button>
    </div>
  );
}
