/** Largest principal whose monthly annuity ≤ `angsuran` at the given rate/months. */
export function maxPlafond(angsuran: number, annualRate: number, months: number): number {
  if (angsuran <= 0 || months <= 0) return 0;
  const im = annualRate / 12;
  if (im === 0) return Math.round(angsuran * months);
  return Math.round((angsuran * (1 - Math.pow(1 + im, -months))) / im);
}

/** Monthly annuity installment for a principal at an annual rate over N months. */
export function anuitas(principal: number, annualRate: number, months: number): number {
  if (months <= 0 || principal <= 0) return 0;
  const im = annualRate / 12;
  if (im === 0) return Math.round(principal / months);
  return Math.round((principal * im) / (1 - Math.pow(1 + im, -months)));
}

/**
 * Max KPR tenor (years) bounded by the borrower's age: the loan must finish by
 * the retirement age (default 56), and is capped (default 25 years).
 */
export function maxTenorByAge(age?: number, retirementAge = 56, cap = 25): number {
  if (age == null) return cap;
  return Math.max(1, Math.min(cap, retirementAge - age));
}

/** Outstanding balance after `paidMonths` of an annuity computed over `totalMonths`. */
function sisaSaldo(principal: number, annualRate: number, totalMonths: number, paidMonths: number): number {
  const im = annualRate / 12;
  if (im === 0) return Math.max(0, principal - (principal / totalMonths) * paidMonths);
  const A = (principal * im) / (1 - Math.pow(1 + im, -totalMonths));
  const f = Math.pow(1 + im, paidMonths);
  return Math.max(0, principal * f - A * ((f - 1) / im));
}

/** One rate window in a KPR rate plan. `years: null` = "rest of the tenor". */
export interface RatePeriod {
  years: number | null;
  rate: number;
}

/** One row of the computed installment schedule (per rate window). */
export interface SchedulePeriod {
  fromYear: number;
  toYear: number;
  years: number;
  rate: number;
  angsuran: number;
  floating: boolean;
}

/**
 * Installment schedule for a fixed-then-floating (or tiered) KPR. At every rate
 * change the annuity is recomputed on the OUTSTANDING balance over the REMAINING
 * tenor — so a fixed promo rate gives a low installment that jumps once the
 * floating/counter rate kicks in.
 */
export function buildSchedule(plafon: number, tenorYears: number, periods: RatePeriod[]): SchedulePeriod[] {
  let balance = plafon;
  let cursor = 0; // years elapsed
  const out: SchedulePeriod[] = [];
  for (const p of periods) {
    const remMonths = (tenorYears - cursor) * 12;
    if (remMonths <= 0 || balance <= 0) break;
    const pYears = p.years == null ? tenorYears - cursor : Math.min(p.years, tenorYears - cursor);
    if (pYears <= 0) break;
    out.push({
      fromYear: cursor + 1,
      toYear: cursor + pYears,
      years: pYears,
      rate: p.rate,
      angsuran: anuitas(balance, p.rate, remMonths),
      floating: p.rate >= 0.12,
    });
    balance = sisaSaldo(balance, p.rate, remMonths, pYears * 12);
    cursor += pYears;
  }
  return out;
}
