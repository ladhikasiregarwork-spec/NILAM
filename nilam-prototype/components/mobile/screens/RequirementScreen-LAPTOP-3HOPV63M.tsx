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
  Info,
  Loader2,
  UploadCloud,
  Sparkles,
  X,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { DOCUMENTS } from "@/data/documents";
import type { DocumentId, DocumentMeta } from "@/types/documents";

interface RequirementScreenProps {
  uploads: Record<string, boolean>;
  onUpload: (key: string, value?: boolean) => void;
  onSubmit: () => void;
  validating: boolean;
  onGoBack?: () => void;
  canGoBack?: boolean;
}

/** Icon per document type. */
const DOC_ICONS: Record<DocumentId, React.ComponentType<{ size?: number; className?: string }>> = {
  ktp:           CreditCard,
  kk:            Users,
  slip_gaji:     FileText,
  mutasi:        Landmark,
  sk_perusahaan: FileSignature,
};

/**
 * RequirementScreen — a SINGLE smart upload menu that accepts MULTIPLE files at
 * once.
 *
 * The user picks several files in one action; the system "auto-detects" each
 * file's type (simulated by categorising the whole batch of still-missing
 * documents) and updates the checklist below. The checklist always shows which
 * documents were uploaded successfully vs. still missing, updating dynamically.
 * Submit needs ≥ 1 doc; any missing documents are flagged on the dashboard.
 */
export function RequirementScreen({
  uploads,
  onUpload,
  onSubmit,
  validating,
  onGoBack,
  canGoBack,
}: RequirementScreenProps) {
  const [detecting, setDetecting] = useState(false);
  const [detectingCount, setDetectingCount] = useState(0);
  const [lastBatch, setLastBatch] = useState<DocumentMeta[]>([]);

  const uploadedCount = DOCUMENTS.filter((d) => uploads[d.id]).length;
  const allUploaded = uploadedCount === DOCUMENTS.length;
  const missingCount = DOCUMENTS.length - uploadedCount;
  const canSubmit = uploadedCount >= 1;

  /**
   * Simulate selecting MULTIPLE files at once → auto-detect each type →
   * categorise the whole batch in one go.
   */
  function handleUpload() {
    if (detecting || allUploaded) return;
    const batch = DOCUMENTS.filter((d) => !uploads[d.id]);
    if (!batch.length) return;
    setDetectingCount(batch.length);
    setDetecting(true);
    setTimeout(() => {
      batch.forEach((d) => onUpload(d.id, true));
      setLastBatch(batch);
      setDetecting(false);
    }, 900);
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto scroll-thin px-3 py-2">
      {/* Title + progress */}
      <div className="mb-2 flex items-end justify-between gap-2">
        <div>
          <h2 className="text-[13px] font-bold text-bri-ink">Upload Dokumen</h2>
          <p className="text-[9px] text-bri-muted">Pilih beberapa berkas sekaligus — sistem deteksi otomatis</p>
        </div>
        <span
          className={cn(
            "rounded-pill px-2 py-0.5 text-[9px] font-semibold",
            allUploaded ? "bg-emerald-50 text-emerald-600" : "bg-bri-bg text-bri-muted"
          )}
        >
          {uploadedCount}/{DOCUMENTS.length}
        </span>
      </div>

      {/* ── Single smart upload menu ─────────────────────────────────── */}
      {allUploaded ? (
        <div className="flex w-full items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
          <CheckCircle2 size={18} className="shrink-0 text-emerald-500" />
          <div className="min-w-0">
            <p className="text-[10px] font-semibold text-emerald-600">Semua dokumen lengkap</p>
            <p className="text-[8px] text-bri-muted">5 dari 5 dokumen terdeteksi &amp; terunggah</p>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={handleUpload}
          disabled={detecting}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed py-4 transition-colors",
            detecting
              ? "border-bri-blue/60 bg-bri-bg"
              : "border-bri-blue/50 bg-bri-bg/40 hover:bg-bri-bg active:scale-[0.99]"
          )}
        >
          {detecting ? (
            <>
              <Loader2 size={22} className="animate-spin text-bri-blue" />
              <span className="text-[10px] font-semibold text-bri-blue">
                Mendeteksi {detectingCount} dokumen…
              </span>
            </>
          ) : (
            <>
              <UploadCloud size={22} className="text-bri-blue" />
              <span className="text-[11px] font-semibold text-bri-blue">Upload Dokumen</span>
              <span className="flex items-center gap-1 text-[8px] text-bri-muted">
                <Sparkles size={9} className="text-bri-blue" />
                JPG/PNG/PDF · bisa pilih beberapa file sekaligus
              </span>
            </>
          )}
        </button>
      )}

      {/* Last auto-detected batch summary */}
      {lastBatch.length > 0 && !detecting && (
        <div className="mt-2 flex items-start gap-1.5 rounded-bubble bg-emerald-50 px-2.5 py-1.5">
          <Sparkles size={11} className="mt-0.5 shrink-0 text-emerald-500" />
          <p className="text-[8.5px] leading-relaxed text-emerald-700">
            {lastBatch.length} dokumen terdeteksi:{" "}
            <span className="font-semibold">{lastBatch.map((d) => d.short).join(", ")}</span>
          </p>
        </div>
      )}

      {/* ── Document checklist (uploaded vs missing) ─────────────────── */}
      <p className="mb-1 mt-3 text-[9px] font-semibold uppercase tracking-[0.14em] text-bri-muted">
        Status Dokumen
      </p>
      <div className="flex flex-col gap-1.5">
        {DOCUMENTS.map((d) => {
          const uploaded = !!uploads[d.id];
          const Icon = DOC_ICONS[d.id];
          return (
            <div
              key={d.id}
              className={cn(
                "flex items-center gap-2.5 rounded-xl border p-2 transition-all",
                uploaded ? "border-emerald-200 bg-emerald-50/60" : "border-dashed border-amber-300 bg-amber-50/40"
              )}
            >
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                  uploaded ? "bg-emerald-100 text-emerald-600" : "bg-amber-100 text-amber-600"
                )}
              >
                <Icon size={14} />
              </div>
              <span className="min-w-0 flex-1 truncate text-[10px] font-semibold text-bri-ink">
                {d.label}
              </span>
              {uploaded ? (
                <button
                  type="button"
                  onClick={() => onUpload(d.id, false)}
                  className="flex shrink-0 items-center gap-1 rounded-pill bg-emerald-100 px-1.5 py-0.5 text-[8px] font-semibold text-emerald-700 transition-colors hover:bg-emerald-200"
                  title="Hapus dokumen ini"
                >
                  <CheckCircle2 size={9} /> Terunggah
                  <X size={9} className="ml-0.5 opacity-60" />
                </button>
              ) : (
                <span className="flex shrink-0 items-center gap-1 rounded-pill bg-amber-100 px-1.5 py-0.5 text-[8px] font-semibold text-amber-700">
                  <AlertTriangle size={9} /> Belum diunggah
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Info box */}
      <div className="mt-2 flex items-start gap-1.5 rounded-bubble bg-bri-bg px-2.5 py-2">
        <Info size={11} className="mt-0.5 shrink-0 text-bri-blue" />
        <p className="text-[8px] leading-relaxed text-bri-blue">
          Cukup satu menu unggah. Sistem mengklasifikasikan tiap berkas ke jenis dokumen yang sesuai.
        </p>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Missing-document hint */}
      {canSubmit && !allUploaded && (
        <p className="mt-1 text-center text-[8px] font-medium text-amber-600">
          {missingCount} dokumen belum diunggah — akan ditandai di dashboard
        </p>
      )}

      {/* Submit */}
      <button
        type="button"
        onClick={canSubmit && !validating ? onSubmit : undefined}
        disabled={!canSubmit || validating}
        className={cn(
          "mt-2 flex w-full items-center justify-center gap-2 rounded-bubble py-2.5 text-[12px] font-semibold text-white transition-all",
          canSubmit && !validating
            ? "hover:opacity-90 active:scale-[0.98]"
            : "cursor-not-allowed opacity-60"
        )}
        style={{
          background: canSubmit
            ? "linear-gradient(135deg, #00529C 0%, #1A6FC4 100%)"
            : "#94A3B8",
        }}
      >
        {validating ? (
          <>
            <Loader2 size={13} className="animate-spin" />
            Mengunggah dokumen…
          </>
        ) : (
          "Submit"
        )}
      </button>

      {/* Back */}
      {canGoBack && (
        <button
          type="button"
          onClick={onGoBack}
          className="mt-2 text-center text-[10px] text-bri-muted transition-colors hover:text-bri-blue"
        >
          ← Kembali
        </button>
      )}
    </div>
  );
}
