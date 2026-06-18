/**
 * Borrower-supplied (or OCR-prefilled) application data, collected on the
 * "Data Diri" step. Prefilled from the KTP/KK where possible, all editable.
 */
export interface UserInput {
  nik?: string;
  nama?: string;
  /** Highest education: SD / SMP / SMA / D3 / S1 / S2 / S3. */
  pendidikan?: string;
  /** Marital status: Belum Kawin / Kawin / Cerai. */
  statusKawin?: string;
  usia?: number;
  /** Desired loan tenor in years. */
  jangkaWaktu?: number;
  /** Down payment (uang muka) in Rupiah. */
  uangMuka?: number;
  jumlahTanggungan?: number;
}

export const PENDIDIKAN_OPSI = ["SD", "SMP", "SMA/SMK", "D3", "S1", "S2", "S3"] as const;
export const STATUS_KAWIN_OPSI = ["Belum Kawin", "Kawin", "Cerai"] as const;
