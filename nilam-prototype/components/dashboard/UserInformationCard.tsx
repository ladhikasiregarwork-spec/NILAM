"use client";

import { UserCircle2, Users, MapPin, AlertTriangle } from "lucide-react";
import type { NodeStatus } from "@/types/orchestration";
import type { KtpExtract, KkExtract } from "@/types/ocrExtract";

interface UserInformationCardProps {
  status: NodeStatus;
  /** OCR-extracted KTP fields. */
  ktp?: KtpExtract;
  /** OCR-extracted KK fields. */
  kk?: KkExtract;
  /** Name override from the Data Diri form (user input). */
  nama?: string;
  /** True when neither KTP nor KK was uploaded. */
  missing?: boolean;
}

const dash = (v?: string) => (v && v.trim() ? v : "—");

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="shrink-0 text-[8px] text-bri-muted">{label}</span>
      <span className="text-right text-[8.5px] font-medium text-bri-ink">{value}</span>
    </div>
  );
}

/**
 * UserInformationCard — "USER INFORMATION". Data diri hasil OCR KTP
 * (Nama, NIK, Gender, Tgl Lahir) + Kartu Keluarga (No. KK, kepala keluarga,
 * anggota) + alamat. Bukan data dummy — diisi dari hasil baca dokumen.
 */
export function UserInformationCard({ status, ktp, kk, nama, missing }: UserInformationCardProps) {
  const ready = status === "success" && !missing;
  const alamat = ktp?.alamat || kk?.alamat;

  return (
    <div className="flex h-full flex-col rounded-xl border border-bri-line bg-white px-2.5 py-2 shadow-soft">
      <span className="mb-1.5 block shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] text-bri-muted">
        User Information
      </span>

      {missing ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-1">
          <AlertTriangle size={14} className="text-amber-500" />
          <span className="text-[8.5px] font-medium text-amber-600">KTP/KK belum diunggah</span>
        </div>
      ) : !ready ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="text-[9px] italic text-bri-muted/40">Menunggu pemrosesan…</span>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-1.5">
          {/* KTP */}
          <div className="flex flex-col gap-0.5">
            <div className="mb-0.5 flex items-center gap-1 text-bri-navy">
              <UserCircle2 size={10} strokeWidth={2} />
              <span className="text-[7.5px] font-bold uppercase tracking-[0.08em]">Data Diri (KTP)</span>
            </div>
            <Row label="Nama" value={dash(nama ?? ktp?.nama)} />
            <Row label="NIK" value={dash(ktp?.nik)} />
            <Row label="Gender" value={dash(ktp?.gender)} />
            <Row label="Tgl Lahir" value={dash(ktp?.tanggalLahir)} />
          </div>

          {/* KK — di bawah Data Diri */}
          <div className="flex flex-col gap-0.5 border-t border-bri-line pt-1.5">
            <div className="mb-0.5 flex items-center gap-1 text-bri-navy">
              <Users size={10} strokeWidth={2} />
              <span className="text-[7.5px] font-bold uppercase tracking-[0.08em]">Kartu Keluarga</span>
            </div>
            <Row label="No. KK" value={dash(kk?.nomorKK)} />
            <Row label="Kepala Kel." value={dash(kk?.kepalaKeluarga)} />
            {kk?.members && kk.members.length > 0 && (
              <div className="mt-0.5 flex flex-col gap-0.5">
                <span className="text-[7px] font-semibold uppercase tracking-[0.08em] text-bri-muted">
                  Anggota Keluarga
                </span>
                {kk.members.map((m, i) => (
                  <div key={`${m.nik ?? m.nama}-${i}`} className="flex items-center justify-between gap-1">
                    <span className={`min-w-0 flex-1 truncate text-[8px] ${m.nama ? "text-bri-ink" : "italic text-bri-muted/60"}`} title={m.nama ?? ""}>
                      {m.nama || "(nama tidak terbaca)"}
                    </span>
                    <span className="shrink-0 text-[7px] tabular-nums text-bri-muted">{m.nik ?? ""}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Alamat */}
          <div className="mt-auto flex items-start gap-1 border-t border-bri-line pt-1">
            <MapPin size={9} className="mt-0.5 shrink-0 text-bri-muted" />
            <span className="text-[8px] text-bri-ink">{dash(alamat)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
