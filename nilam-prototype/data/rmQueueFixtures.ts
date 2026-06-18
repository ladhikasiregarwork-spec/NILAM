/**
 * Demo entries for the Relationship Manager (RM) survey queue. These are static
 * placeholder applications so the RM panel always shows a realistic queue
 * alongside the live application (collateral ≥ Rp500 juta). Approving/rejecting
 * a demo entry is cosmetic only — it does not affect the live customer flow.
 */
export interface RmQueueItem {
  id: string;
  nama: string;
  kota: string;
  /** Submitted collateral price (IDR). */
  hargaAgunan: number;
  luasBangunan: number;
  luasTanah: number;
  /** NPW model fair-value estimate (IDR). */
  npw: number;
  /** Application date (display string). */
  tanggalAjuan: string;
}

export const RM_QUEUE_DEMO: RmQueueItem[] = [
  {
    id: "rm-budi",
    nama: "Budi Santoso",
    kota: "Depok",
    hargaAgunan: 720_000_000,
    luasBangunan: 60,
    luasTanah: 90,
    npw: 705_000_000,
    tanggalAjuan: "10 Jun 2026",
  },
  {
    id: "rm-citra",
    nama: "Citra Dewi",
    kota: "Bekasi",
    hargaAgunan: 645_000_000,
    luasBangunan: 54,
    luasTanah: 72,
    npw: 632_000_000,
    tanggalAjuan: "11 Jun 2026",
  },
];
