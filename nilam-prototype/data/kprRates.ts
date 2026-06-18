/**
 * BRI KPR interest schemes — from the BRI Consumer Expo 2026 rate sheet.
 * `rate` is the indicative effective rate p.a. used for the angsuran estimate
 * (the promo/first-period rate for fixed/tiered schemes). `note` spells out the
 * full schedule. Valid until 30 Juni 2026.
 */
export interface KprScheme {
  id: string;
  label: string;
  rateLabel: string;
  /** Indicative rate used for the displayed installment. */
  rate: number;
  /** Allowed tenor range in years. */
  minTenor: number;
  maxTenor: number;
  tiered?: boolean;
  note: string;
}

export const KPR_SCHEMES: KprScheme[] = [
  { id: "fixed1", label: "Fixed 1 Tahun", rateLabel: "1,75%", rate: 0.0175, minTenor: 5, maxTenor: 25, note: "Fixed 1 thn, lalu counter rate" },
  { id: "fixed3", label: "Fixed 3 Tahun", rateLabel: "2,65%", rate: 0.0265, minTenor: 15, maxTenor: 25, note: "Fixed 3 thn, lalu counter rate" },
  { id: "fixed5", label: "Fixed 5 Tahun", rateLabel: "3,40%", rate: 0.034, minTenor: 15, maxTenor: 25, note: "Fixed 5 thn, lalu counter rate" },
  { id: "berjenjang", label: "Berjenjang", rateLabel: "2,95% → bertahap", rate: 0.0295, minTenor: 10, maxTenor: 20, tiered: true, note: "Thn 1-3: 2,95% · 4-6: 6,95% · 7+: 8,95% · lalu counter rate" },
  { id: "fixedall", label: "Fixed All Tenor", rateLabel: "7,25–8,00%", rate: 0.0775, minTenor: 1, maxTenor: 25, note: "Fixed sepanjang tenor: 1-4 thn 7,25% · 5-10 thn 7,75% · 11-25 thn 8,00%" },
];

/** Rate used for the angsuran estimate, given a tenor (handles Fixed All Tenor tiers). */
export function schemeRate(scheme: KprScheme, tenorYears: number): number {
  if (scheme.id === "fixedall") {
    if (tenorYears <= 4) return 0.0725;
    if (tenorYears <= 10) return 0.0775;
    return 0.08;
  }
  return scheme.rate;
}

/** Floating / counter rate p.a. applied after the fixed/tiered promo period. */
export const FLOATING_RATE = 0.125;

/**
 * Full rate plan over the tenor: the fixed/tiered promo windows, then the
 * floating (counter) rate for the remainder. Fixed-All-Tenor stays fixed.
 */
export function ratePlan(scheme: KprScheme, tenorYears: number, floating = FLOATING_RATE) {
  switch (scheme.id) {
    case "fixed1":
      return [{ years: 1, rate: 0.0175 }, { years: null, rate: floating }];
    case "fixed3":
      return [{ years: 3, rate: 0.0265 }, { years: null, rate: floating }];
    case "fixed5":
      return [{ years: 5, rate: 0.034 }, { years: null, rate: floating }];
    case "berjenjang":
      return [
        { years: 3, rate: 0.0295 },
        { years: 3, rate: 0.0695 },
        { years: 4, rate: 0.0895 },
        { years: null, rate: floating },
      ];
    case "fixedall":
      return [{ years: null, rate: schemeRate(scheme, tenorYears) }];
    default:
      return [{ years: null, rate: scheme.rate }];
  }
}
