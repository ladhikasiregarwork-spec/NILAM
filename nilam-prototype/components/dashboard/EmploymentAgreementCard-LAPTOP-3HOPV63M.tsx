"use client";

import { FileSignature, CalendarRange } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRupiah } from "@/lib/formatRupiah";
import type { NodeStatus } from "@/types/orchestration";
import type { EmploymentAgreement } from "@/types/profile";

interface EmploymentAgreementCardProps {
  /** Gates the card: data only shows once the extraction step succeeds. */
  status: NodeStatus;
  agreement: EmploymentAgreement | undefined;
  /** Header label — defaults to "Perjanjian Kerja". */
  title?: string;
  /** True when the document was not uploaded — show a "belum diunggah" state. */
  missing?: boolean;
}

/** Label + value row. */
function AgreementRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-1">
      <span className="shrink-0 text-[8.5px] text-bri-muted">{label}</span>
      <span className="text-right text-[8.5px] font-medium text-bri-ink">{value}</span>
    </div>
  );
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
}: EmploymentAgreementCardProps) {
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
      </div>

      {/* Body — field rows + base-salary highlight, footer pinned */}
      <div className="flex flex-1 flex-col justify-between">
        <div className="flex flex-col gap-0.5">
          <AgreementRow label="Perusahaan" value={agreement.perusahaan} />
          <AgreementRow label="Jabatan" value={agreement.jabatan} />
          <AgreementRow label="Status" value={agreement.statusKepegawaian} />
          <AgreementRow label="Masa Kerja" value={agreement.masaKerja} />
        </div>

        {/* Gaji pokok highlight */}
        <div className="mt-1 flex items-center justify-between rounded-lg border border-bri-line/70 bg-bri-bg/50 px-2 py-1">
          <span className="text-[8.5px] text-bri-muted">Gaji Pokok</span>
          <span className="text-[11px] font-bold text-bri-navy tabular-nums">
            {formatRupiah(agreement.gajiPokok)}
          </span>
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
