"use client";

import { useState } from "react";
import { FileSignature, CalendarRange, Pencil } from "lucide-react";
import { cn } from "@/lib/cn";
import type { NodeStatus } from "@/types/orchestration";
import type { EmploymentAgreement } from "@/types/profile";

type EditableField = "perusahaan" | "jabatan" | "statusKepegawaian" | "masaKerja";
const EDITABLE: { key: EditableField; label: string }[] = [
  { key: "perusahaan", label: "Perusahaan" },
  { key: "jabatan", label: "Jabatan" },
  { key: "statusKepegawaian", label: "Status" },
  { key: "masaKerja", label: "Masa Kerja" },
];

interface EmploymentAgreementCardProps {
  /** Gates the card: data only shows once the extraction step succeeds. */
  status: NodeStatus;
  agreement: EmploymentAgreement | undefined;
  /** Header label — defaults to "Perjanjian Kerja". */
  title?: string;
  /** True when the document was not uploaded — show a "belum diunggah" state. */
  missing?: boolean;
  /** Optional source badge, e.g. "Hasil OCR" when data came from a real PDF. */
  sourceLabel?: string;
}

/**
 * EmploymentAgreementCard — profile extracted from the employment agreement
 * (perjanjian kerja): employer, role, status, tenure, base salary, and the
 * contract period. Pending until the extraction step (`status`) succeeds.
 */
export function EmploymentAgreementCard({
  status,
  agreement,
  title = "Perjanjian Kerja",
  missing,
  sourceLabel,
}: EmploymentAgreementCardProps) {
  // Inline edits (default = OCR value, tracked until the user types).
  const [edits, setEdits] = useState<Partial<Record<EditableField, string>>>({});
  const isSuccess = status === "success" && !missing;

  if (!isSuccess || !agreement) {
    return (
      <div className="flex h-full flex-col rounded-xl border border-bri-line bg-white px-2.5 py-2 shadow-soft">
        <span className="mb-1.5 block shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
          {title}
        </span>
        <div className="flex flex-1 items-center gap-2">
          <div
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-dashed bg-bri-bg/40",
              missing ? "border-amber-300" : "border-bri-line"
            )}
          >
            <FileSignature
              size={20}
              className={missing ? "text-amber-500/70" : "text-bri-muted/40"}
              strokeWidth={1.5}
            />
          </div>
          <p className={cn("text-[9px]", missing ? "font-medium text-amber-600" : "italic text-bri-muted/40")}>
            {missing ? "Dokumen belum diunggah" : "Menunggu dokumen kontrak…"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-bri-line bg-white px-2.5 py-2 shadow-soft">
      {/* Header */}
      <div className="mb-1.5 flex shrink-0 items-center gap-1">
        <FileSignature size={10} className="text-bri-navy" strokeWidth={2} />
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
          {title}
        </span>
        <span className="ml-auto flex items-center gap-1">
          {sourceLabel && (
            <span className="rounded-pill bg-bri-navy/10 px-1.5 py-px text-[7px] font-semibold text-bri-navy">
              {sourceLabel}
            </span>
          )}
          <Pencil size={8} className="text-bri-muted/60" />
        </span>
      </div>

      {/* Body — editable field rows (default from OCR), footer pinned */}
      <div className="flex flex-1 flex-col justify-between">
        <div className="flex flex-col gap-0.5">
          {EDITABLE.map((f) => (
            <div key={f.key} className="flex items-center justify-between gap-1">
              <span className="shrink-0 text-[8.5px] text-bri-muted">{f.label}</span>
              <input
                value={edits[f.key] ?? String(agreement[f.key] ?? "")}
                onChange={(e) => setEdits((p) => ({ ...p, [f.key]: e.target.value }))}
                className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-1 py-0.5 text-right text-[8.5px] font-medium text-bri-ink hover:border-bri-line focus:border-bri-blue focus:bg-white focus:outline-none"
              />
            </div>
          ))}
        </div>

        {/* Contract period — pinned at bottom */}
        <div className="mt-1 flex shrink-0 items-center gap-1 border-t border-bri-line pt-1.5">
          <CalendarRange size={10} className="shrink-0 text-bri-navy/70" strokeWidth={2} />
          <span className="text-[8.5px] text-bri-ink">
            {agreement.tanggalMulai}
            <span className="px-1 text-bri-muted">→</span>
            {agreement.tanggalBerakhir}
          </span>
        </div>
      </div>
    </div>
  );
}
