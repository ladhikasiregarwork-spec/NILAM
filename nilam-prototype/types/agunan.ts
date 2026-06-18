/**
 * Agunan (collateral / property) data for the KPR flow. Filled either MANUALLY
 * by the user, or extracted from a property listing LINK (Rumah123) via
 * /api/agunan/from-link.
 */
export interface AgunanData {
  /** Building area (m²). */
  luasBangunan?: number;
  /** Land area (m²). */
  luasTanah?: number;
  provinsi?: string;
  kota?: string;
  kecamatan?: string;
  kelurahan?: string;
  kodepos?: string;
  /** Property price (IDR). */
  harga?: number;
  /** Coordinates (only when sourced from a link). */
  lat?: number;
  lon?: number;
  /** Where the data came from. */
  sumber?: "link" | "manual";
  /** Original listing URL when sumber === "link". */
  url?: string;
  /** Primary property photo URL (from the listing's og:image), when sourced from a link. */
  imageUrl?: string;
  /** All property photo URLs from the listing (gallery). */
  imageUrls?: string[];
}
