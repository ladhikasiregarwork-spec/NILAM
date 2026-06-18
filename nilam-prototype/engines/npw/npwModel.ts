import type { AgunanData } from "@/types/agunan";

/**
 * NPW — Nilai Pasar Wajar (fair market value) of the collateral property.
 *
 * NPW is the OUTPUT of an appraisal model — it is NOT a user input. The real
 * model will be dropped into this folder later; replace the body of
 * `computeNpw` with that model (it can read luas tanah/bangunan, lokasi, harga
 * listing, dll. dari `agunan`).
 *
 * For now this is a PLACEHOLDER that returns the listing price as a proxy, so
 * the dashboard has a value to display. `placeholder: true` flags that the real
 * model isn't wired yet.
 */
export interface NpwResult {
  value?: number;
  placeholder: boolean;
}

export function computeNpw(agunan?: AgunanData): NpwResult {
  if (!agunan || agunan.harga == null) {
    return { value: undefined, placeholder: true };
  }
  // TODO: ganti dengan model NPW Anda (nilai pasar wajar).
  return { value: agunan.harga, placeholder: true };
}
