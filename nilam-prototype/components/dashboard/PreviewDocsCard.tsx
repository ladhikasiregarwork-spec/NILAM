"use client";

import { CreditCard, Users, FileText, Landmark, FileSignature, File, ExternalLink, FolderOpen, Folder } from "lucide-react";
import type { ClassifyLabel, PreviewDoc } from "@/types/ocrExtract";

interface PreviewDocsCardProps {
  docs: PreviewDoc[];
}

/** File label per type. */
const PRETTY: Record<ClassifyLabel, string> = {
  ktp: "KTP",
  kk: "Kartu Keluarga",
  slip: "Slip Gaji",
  mutasi: "Mutasi Rekening",
  sk: "SK Perusahaan",
  unknown: "Dokumen",
};

/** Folder name per type + display order. */
const FOLDER_NAME: Record<ClassifyLabel, string> = {
  ktp: "KTP",
  kk: "KK",
  sk: "SK Perusahaan",
  slip: "Slip Gaji",
  mutasi: "Mutasi Rekening",
  unknown: "Lainnya",
};
const FOLDER_ORDER: ClassifyLabel[] = ["ktp", "kk", "sk", "slip", "mutasi", "unknown"];

const ICONS: Record<ClassifyLabel, React.ComponentType<{ size?: number; className?: string }>> = {
  ktp: CreditCard,
  kk: Users,
  slip: FileText,
  mutasi: Landmark,
  sk: FileSignature,
  unknown: File,
};

const ext = (name: string) => (name.includes(".") ? `.${name.split(".").pop()}` : "");

/**
 * PreviewDocsCard — bottom of the dashboard. Uploaded documents grouped into
 * FOLDERS by classification (KTP, KK, SK Perusahaan, Slip Gaji, Mutasi
 * Rekening), each file RENAMED by type and linked to view the original.
 */
export function PreviewDocsCard({ docs }: PreviewDocsCardProps) {
  if (docs.length === 0) return null;

  // Number files per type (only when >1), then bucket them into folders.
  const totals: Partial<Record<ClassifyLabel, number>> = {};
  docs.forEach((d) => (totals[d.type] = (totals[d.type] ?? 0) + 1));
  const seen: Partial<Record<ClassifyLabel, number>> = {};
  const buckets: Partial<Record<ClassifyLabel, { name: string; url: string; originalName: string }[]>> = {};
  docs.forEach((d) => {
    seen[d.type] = (seen[d.type] ?? 0) + 1;
    const base = PRETTY[d.type] ?? "Dokumen";
    const name = (totals[d.type] ?? 0) > 1 ? `${base} #${seen[d.type]}${ext(d.originalName)}` : `${base}${ext(d.originalName)}`;
    (buckets[d.type] ??= []).push({ name, url: d.url, originalName: d.originalName });
  });

  const folders = FOLDER_ORDER.filter((t) => buckets[t]?.length);

  return (
    <div className="rounded-xl border border-bri-line bg-white px-3 py-2 shadow-soft">
      <div className="mb-1.5 flex items-center gap-1">
        <FolderOpen size={11} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">Preview Dokumen</span>
        <span className="ml-1 rounded-pill bg-bri-bg px-1.5 py-px text-[7.5px] font-semibold text-bri-muted">{docs.length} file</span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {folders.map((type) => {
          const Icon = ICONS[type] ?? File;
          const files = buckets[type]!;
          return (
            <div key={type} className="overflow-hidden rounded-lg border border-bri-line/70">
              {/* Folder header */}
              <div className="flex items-center gap-1.5 bg-bri-bg/60 px-2 py-1">
                <Folder size={11} className="shrink-0 text-bri-navy" />
                <span className="flex-1 truncate text-[8.5px] font-semibold text-bri-ink">{FOLDER_NAME[type]}</span>
                <span className="rounded-pill bg-white px-1.5 py-px text-[7px] font-semibold text-bri-muted">{files.length}</span>
              </div>
              {/* Files */}
              <div className="divide-y divide-bri-line/50">
                {files.map((f, i) => (
                  <a
                    key={i}
                    href={f.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-1.5 px-2 py-1 transition-colors hover:bg-bri-blue/5"
                    title={`Buka ${f.originalName}`}
                  >
                    <Icon size={11} className="shrink-0 text-bri-navy/70" />
                    <span className="min-w-0 flex-1 truncate text-[8.5px] text-bri-ink">{f.name}</span>
                    <ExternalLink size={10} className="shrink-0 text-bri-muted group-hover:text-bri-blue" />
                  </a>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-[7px] text-bri-muted/70">Klik file untuk membuka dokumen asli. Dikelompokkan per folder sesuai hasil klasifikasi.</p>
    </div>
  );
}
