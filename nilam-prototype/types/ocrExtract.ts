/**
 * Normalized shapes returned by the Next.js OCR proxy routes
 * (app/api/ocr/*). The proxy maps each FastAPI service's raw response into
 * these flat, UI-friendly objects so the frontend never deals with the Python
 * service's internal JSON.
 *
 * Sources:
 *   - SlipGajiExtract   ← slip-gaji-ocr  /parse  (summary.periode/nasabah/dokumen)
 *   - SkPerusahaanExtract ← keterangan-kerja-ocr /parse (summary.dokumen/pemohon)
 */

/** One salary slip = one payment date. */
export interface SlipRecord {
  tanggalPembayaran?: string;
  totalUpah?: number;
  totalPotongan?: number;
  /** Take-home pay = totalUpah − totalPotongan. */
  thp?: number;
  thr?: number;
  bonus?: number;
  /** Upah/Gaji Pokok line from the slip. */
  gajiPokok?: number;
  /** Sum of all "Tunjangan ..." earning lines (excl. THR). */
  tunjangan?: number;
  /** Deduction line items for bonus / THR / cuti (to net out of potongan). */
  potonganBonus?: number;
  potonganThr?: number;
  potonganCuti?: number;
  fileName?: string;
}

/** Salary-slip extraction: one record per uploaded slip (per payment date). */
export interface SlipGajiExtract {
  records: SlipRecord[];
}

export interface SkPerusahaanExtract {
  perusahaan?: string;
  jabatan?: string;
  statusKepegawaian?: string;
  masaKerja?: string;
  tanggalMulai?: string;
  tanggalBerakhir?: string;
  namaPekerja?: string;
  nik?: string;
  nomorSurat?: string;
  tanggalSurat?: string;
  fileName?: string;
  needsPassword?: boolean;
  /** True when the document was classified as NOT a Surat Keterangan Kerja. */
  rejected?: boolean;
}

/** Fields extracted from a KTP (Tesseract + regex). */
export interface KtpExtract {
  nik?: string;
  nama?: string;
  gender?: string;
  tempatLahir?: string;
  tanggalLahir?: string;
  alamat?: string;
  statusPerkawinan?: string;
  fileName?: string;
}

export interface KkMember {
  nama: string;
  hubungan: string;
  nik?: string;
}

/** Fields extracted from a Kartu Keluarga (Tesseract + regex). */
export interface KkExtract {
  nomorKK?: string;
  kepalaKeluarga?: string;
  alamat?: string;
  members?: KkMember[];
  fileName?: string;
}

/** One transaction parsed from a bank statement (mutasi rekening). */
export interface MutasiTxn {
  tanggal: string;
  remark: string;
  nominal: number;
  /** "Debit" | "Kredit". */
  dk: string;
  klasifikasi: string;
}

/** Bank-statement extraction result. */
export interface MutasiExtract {
  transactions: MutasiTxn[];
  noRekening?: string;
  count: number;
  totalKredit: number;
  totalDebet: number;
  /** The credit nominal detected as recurring salary (gaji). */
  gajiNominal?: number;
  /** Total per income classification (Gaji, THR, Bonus, Tunjangan, …). */
  ringkasan?: Record<string, number>;
  fileName?: string | string[];
}

/** OCR results held in flow state, keyed by the document. */
export interface OcrResults {
  slipGaji?: SlipGajiExtract;
  skPerusahaan?: SkPerusahaanExtract;
  ktp?: KtpExtract;
  kk?: KkExtract;
  mutasi?: MutasiExtract;
}

/** Classifier label for one uploaded file (from the local classifier). */
export type ClassifyLabel = "ktp" | "kk" | "slip" | "mutasi" | "sk" | "unknown";

/** One file's classification result returned to the browser. */
export interface ClassifyResult {
  fileName: string;
  type: ClassifyLabel;
  confidence: string;
  /** KTP fields extracted in the same OCR pass (avoids a second /extract-ktp). */
  extract?: KtpExtract;
}

/** An uploaded document kept for preview (blob URL + its classified type). */
export interface PreviewDoc {
  type: ClassifyLabel;
  /** Object URL (URL.createObjectURL) for viewing. */
  url: string;
  /** Original uploaded filename (for the extension). */
  originalName: string;
}

/** Response envelope returned by the proxy routes to the browser. */
export interface OcrProxyResponse<T> {
  ok: boolean;
  extract?: T;
  error?: string;
  /** Raw service payload, kept for debugging. */
  raw?: unknown;
}
