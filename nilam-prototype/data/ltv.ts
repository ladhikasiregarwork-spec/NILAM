/**
 * KPR LTV matrix (from the BRI collateral grid). Used to size the plafon from
 * the collateral: plafon agunan = NPW (Nilai Pasar Wajar) × LTV.
 */

export type AgunanKategori = "baru" | "lama";
export type DeveloperTier = "tier1" | "local_champion" | "tier2" | "tier3";
export type PropertiTipe = "tapak" | "apartemen" | "ruko";
export type UkuranTipe = "gt70" | "mid" | "lt21"; // >70 · 21-70 · <21
export type RumahLamaJenis = "secondary" | "refinancing";
export type RangeHarga = "lt5" | "mid" | "gt15";

export const TIER_LABEL: Record<DeveloperTier, string> = {
  tier1: "Developer Tier 1",
  local_champion: "Local Champion",
  tier2: "Developer Tier 2",
  tier3: "Developer Tier 3",
};
export const PROPERTI_LABEL: Record<PropertiTipe, string> = {
  tapak: "Rumah Tapak",
  apartemen: "Apartemen/Rusun",
  ruko: "Ruko/Rukan",
};
export const UKURAN_LABEL: Record<UkuranTipe, string> = {
  gt70: "Tipe > 70",
  mid: "Tipe 21-70",
  lt21: "Tipe < 21",
};
export const LAMA_LABEL: Record<RumahLamaJenis, string> = {
  secondary: "Secondary",
  refinancing: "Refinancing",
};
export const RANGE_LABEL: Record<RangeHarga, string> = {
  lt5: "< Rp 5 M",
  mid: "Rp 5 M – 15 M",
  gt15: "> Rp 15 M",
};

// LTV_BARU[tier][properti][ukuran]
const LTV_BARU: Record<DeveloperTier, Record<PropertiTipe, Record<UkuranTipe, number>>> = {
  tier1: {
    tapak: { gt70: 0.95, mid: 0.95, lt21: 0.95 },
    apartemen: { gt70: 0.85, mid: 0.9, lt21: 0.9 },
    ruko: { gt70: 0.9, mid: 0.9, lt21: 0.9 },
  },
  local_champion: {
    tapak: { gt70: 0.9, mid: 0.9, lt21: 0.9 },
    apartemen: { gt70: 0.8, mid: 0.85, lt21: 0.85 },
    ruko: { gt70: 0.85, mid: 0.85, lt21: 0.85 },
  },
  tier2: {
    tapak: { gt70: 0.9, mid: 0.9, lt21: 0.9 },
    apartemen: { gt70: 0.85, mid: 0.85, lt21: 0.85 },
    ruko: { gt70: 0.8, mid: 0.8, lt21: 0.8 },
  },
  tier3: {
    tapak: { gt70: 0.85, mid: 0.85, lt21: 0.85 },
    apartemen: { gt70: 0.8, mid: 0.8, lt21: 0.8 },
    ruko: { gt70: 0.75, mid: 0.75, lt21: 0.75 },
  },
};

const LTV_SECONDARY: Record<RangeHarga, number> = { lt5: 0.9, mid: 0.85, gt15: 0.8 };
const LTV_REFINANCING = 0.7;

export function rangeHarga(harga?: number): RangeHarga {
  if (harga == null) return "mid";
  if (harga < 5_000_000_000) return "lt5";
  if (harga <= 15_000_000_000) return "mid";
  return "gt15";
}

export function ltvBaru(tier: DeveloperTier, prop: PropertiTipe, ukuran: UkuranTipe): number {
  return LTV_BARU[tier][prop][ukuran];
}

export function ltvLama(jenis: RumahLamaJenis, harga?: number): number {
  return jenis === "refinancing" ? LTV_REFINANCING : LTV_SECONDARY[rangeHarga(harga)];
}

/** The editable collateral classification, shared across the dashboard + offer. */
export interface AgunanKlasifikasi {
  kategori: AgunanKategori;
  tier: DeveloperTier;
  prop: PropertiTipe;
  ukuran: UkuranTipe;
  jenisLama: RumahLamaJenis;
}

export const DEFAULT_KLASIFIKASI: AgunanKlasifikasi = {
  kategori: "baru",
  tier: "tier1",
  prop: "tapak",
  ukuran: "gt70",
  jenisLama: "secondary",
};

export function ltvFromKlas(k: AgunanKlasifikasi, harga?: number): number {
  return k.kategori === "baru" ? ltvBaru(k.tier, k.prop, k.ukuran) : ltvLama(k.jenisLama, harga);
}
