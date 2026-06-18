import type { SlipGajiExtract, SkPerusahaanExtract } from "@/types/ocrExtract";

/** Coerce a service value (number or "Rp1.234.000" string) into a number. */
export function toNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const digits = value.replace(/[^\d.-]/g, "");
    if (!digits) return undefined;
    const n = Number(digits);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

/** First non-empty string from an array (the services return arrays of values). */
function firstOf(arr: unknown): string | undefined {
  if (Array.isArray(arr)) {
    for (const v of arr) if (typeof v === "string" && v.trim()) return v;
  }
  return undefined;
}

/** Map the slip-gaji-ocr /parse response → SlipGajiExtract. */
export function mapSlipGaji(data: any): SlipGajiExtract {
  const summary = data?.summary ?? {};
  // NOTE: this legacy mapper (slip-gaji-ocr service) is superseded by the local
  // /extract-slip extractor. Kept only so the old route still type-checks.
  const total = summary?.periode?.total ?? {};
  const avg = summary?.periode?.rata_rata ?? {};
  const doc0 = (summary?.dokumen ?? [])[0] ?? {};
  const upah = toNumber(total.total_dibayar ?? avg.total_dibayar ?? doc0.total_dibayar);
  const potongan = toNumber(total.potongan ?? avg.potongan);
  return {
    records: [
      {
        totalUpah: upah,
        totalPotongan: potongan,
        thp: upah != null && potongan != null ? upah - potongan : upah,
        fileName: (data?.uploaded_files ?? [])[0],
      },
    ],
  };
}

/** Map the keterangan-kerja-ocr /parse response → SkPerusahaanExtract. */
export function mapSkPerusahaan(data: any): SkPerusahaanExtract {
  const summary = data?.summary ?? {};
  const doc0 = (summary?.dokumen ?? [])[0] ?? {};
  const errors = summary?.kesalahan ?? [];
  return {
    perusahaan: doc0.nama_institusi ?? firstOf(summary?.pemohon?.nama_institusi),
    jabatan: doc0.jabatan,
    statusKepegawaian: doc0.status_karyawan,
    masaKerja: doc0.masa_kerja,
    tanggalMulai: doc0.tanggal_mulai_kerja,
    tanggalBerakhir: doc0.tanggal_akhir_kerja,
    namaPekerja: doc0.nama_pekerja ?? firstOf(summary?.pemohon?.nama_pekerja),
    nik: doc0.nik ?? firstOf(summary?.pemohon?.nik),
    nomorSurat: doc0.nomor_surat,
    tanggalSurat: doc0.tanggal_surat,
    fileName: (data?.uploaded_files ?? [])[0],
    needsPassword: !!data?.needs_password,
    rejected: errors.length > 0 && (summary?.dokumen ?? []).length === 0,
  };
}
