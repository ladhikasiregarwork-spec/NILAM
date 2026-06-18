"use client";

import { useState } from "react";
import {
  CreditCard,
  Users,
  FileText,
  Landmark,
  FileSignature,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  UploadCloud,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { DOCUMENTS } from "@/data/documents";
import type { DocumentId } from "@/types/documents";
import type { ClassifyResult } from "@/types/ocrExtract";

interface RequirementScreenProps {
  uploads: Record<string, boolean>;
  docCounts: Partial<Record<DocumentId, number>>;
  classifyAndUpload: (
    files: File[],
  ) => Promise<{ ok: boolean; results?: ClassifyResult[]; error?: string }>;
  clearUploads: () => void;
  onSubmit: () => void;
  validating: boolean;
  onGoBack?: () => void;
  canGoBack?: boolean;
}

const DOC_ICONS: Record<DocumentId, React.ComponentType<{ size?: number; className?: string }>> = {
  ktp:           CreditCard,
  kk:            Users,
  slip_gaji:     FileText,
  mutasi:        Landmark,
  sk_perusahaan: FileSignature,
};

/**
 * RequirementScreen — SATU menu upload untuk semua dokumen (KTP, KK, Slip Gaji,
 * SK, Mutasi). Tiap file diklasifikasi otomatis oleh classifier lokal, lalu
 * di-OCR sesuai jenisnya (KTP via PaddleOCR lokal; sisanya Tesseract/regex).
 */
export function RequirementScreen({
  uploads,
  docCounts,
  classifyAndUpload,
  clearUploads,
  onSubmit,
  validating,
  onGoBack,
  canGoBack,
}: RequirementScreenProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  const uploadedCount = DOCUMENTS.filter((d) => uploads[d.id]).length;
  const allUploaded = uploadedCount === DOCUMENTS.length;
  const canSubmit = uploadedCount >= 1;

  async function handleClassify(list: FileList) {
    const arr = Array.from(list);
    if (!arr.length) return;
    setError(undefined);
    setLoading(true);
    const res = await classifyAndUpload(arr);
    setLoading(false);
    if (!res.ok) {
      setError(res.error || "Gagal memproses dokumen");
    }
  }

  function resetUploads() {
    clearUploads();
    setError(undefined);
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-3 py-2">
      {/* Title + progress */}
      <div className="mb-2 flex items-end justify-between gap-2">
        <div>
          <h2 className="text-[13px] font-bold text-bri-ink">Upload Dokumen</h2>
          <p className="text-[9px] text-bri-muted">Semua dokumen · jenis dideteksi otomatis</p>
        </div>
        <span className={cn("rounded-pill px-2 py-0.5 text-[9px] font-semibold", allUploaded ? "bg-emerald-50 text-emerald-600" : "bg-bri-bg text-bri-muted")}>
          {uploadedCount}/{DOCUMENTS.length}
        </span>
      </div>

      {/* SATU menu untuk semua dokumen (KTP, KK, Slip, SK, Mutasi) */}
      <label className={cn("flex w-full cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed py-4 transition-colors", loading ? "border-bri-blue/60 bg-bri-bg" : "border-bri-blue/50 bg-bri-bg/40 hover:bg-bri-bg")}>
        {loading ? (
          <>
            <Loader2 size={18} className="animate-spin text-bri-blue" />
            <span className="text-[9px] font-semibold text-bri-blue">Mendeteksi & membaca dokumen…</span>
          </>
        ) : (
          <>
            <UploadCloud size={18} className="text-bri-blue" />
            <span className="text-[10px] font-semibold text-bri-blue">Upload Dokumen</span>
            <span className="text-[8px] text-bri-muted">KTP · KK · Slip Gaji · SK · Mutasi — bisa banyak file sekaligus</span>
          </>
        )}
        <input
          type="file"
          accept="application/pdf,image/*"
          multiple
          className="hidden"
          disabled={loading}
          onChange={(e) => {
            const list = e.target.files;
            if (list && list.length) handleClassify(list);
            e.target.value = "";
          }}
        />
      </label>
      {error && (
        <p className="mt-1 flex items-center gap-1 text-[8.5px] font-medium text-red-500">
          <AlertTriangle size={10} /> {error}
        </p>
      )}

      {/* Checklist */}
      <div className="mb-1 mt-3 flex items-center justify-between">
        <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-bri-muted">Status Dokumen</p>
        <button type="button" onClick={resetUploads} className="flex items-center gap-1 text-[8px] font-medium text-bri-muted transition-colors hover:text-bri-blue">
          <RefreshCw size={9} /> Mulai ulang
        </button>
      </div>
      <div className="flex flex-col gap-1">
        {DOCUMENTS.map((d) => {
          const Icon = DOC_ICONS[d.id];
          const uploaded = !!uploads[d.id];
          const count = docCounts[d.id] ?? 0;
          const showCount = (d.id === "slip_gaji" || d.id === "mutasi") && count > 0;
          return (
            <div key={d.id} className={cn("flex items-center gap-2 rounded-lg border px-2 py-1 transition-all", uploaded ? "border-emerald-200 bg-emerald-50/60" : "border-dashed border-amber-300 bg-amber-50/40")}>
              <div className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded", uploaded ? "bg-emerald-100 text-emerald-600" : "bg-amber-100 text-amber-600")}>
                <Icon size={11} />
              </div>
              <span className="min-w-0 flex-1 truncate text-[9px] font-semibold text-bri-ink">{d.label}</span>
              {showCount && <span className="shrink-0 rounded-pill bg-emerald-100 px-1.5 py-px text-[7px] font-semibold text-emerald-700">{count} file</span>}
              {uploaded ? (
                <CheckCircle2 size={12} className="shrink-0 text-emerald-500" />
              ) : (
                <AlertTriangle size={11} className="shrink-0 text-amber-500" />
              )}
            </div>
          );
        })}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {canSubmit && !allUploaded && (
        <p className="mt-1 text-center text-[8px] font-medium text-amber-600">
          {DOCUMENTS.length - uploadedCount} dokumen belum diunggah — akan ditandai di dashboard
        </p>
      )}

      {/* Submit */}
      <button
        type="button"
        onClick={canSubmit && !validating ? onSubmit : undefined}
        disabled={!canSubmit || validating}
        className={cn(
          "mt-2 flex w-full items-center justify-center gap-2 rounded-bubble py-2.5 text-[12px] font-semibold text-white transition-all",
          canSubmit && !validating ? "hover:opacity-90 active:scale-[0.98]" : "cursor-not-allowed opacity-60"
        )}
        style={{ background: canSubmit ? "linear-gradient(135deg, #00529C 0%, #1A6FC4 100%)" : "#94A3B8" }}
      >
        {validating ? (
          <>
            <Loader2 size={13} className="animate-spin" />
            Memproses…
          </>
        ) : (
          "Lanjut"
        )}
      </button>

      {canGoBack && (
        <button type="button" onClick={onGoBack} className="mt-2 text-center text-[10px] text-bri-muted transition-colors hover:text-bri-blue">
          ← Kembali
        </button>
      )}
    </div>
  );
}
