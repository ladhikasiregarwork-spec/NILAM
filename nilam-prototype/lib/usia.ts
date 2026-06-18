/** Parse a KTP birthdate string ("DD-MM-YYYY" or "DD/MM/YYYY") → Date. */
export function parseTanggalLahir(s?: string): Date | undefined {
  if (!s) return undefined;
  const m = s.match(/(\d{1,2})[-/](\d{1,2})[-/](\d{4})/);
  if (!m) return undefined;
  const date = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  return Number.isNaN(date.getTime()) ? undefined : date;
}

/** Age in whole years at `now` (defaults to today). */
export function hitungUsia(birth?: Date, now: Date = new Date()): number | undefined {
  if (!birth) return undefined;
  let age = now.getFullYear() - birth.getFullYear();
  const md = now.getMonth() - birth.getMonth();
  if (md < 0 || (md === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 0 && age < 120 ? age : undefined;
}

/** Convenience: age straight from a KTP birthdate string. */
export function usiaDariKtp(tanggalLahir?: string): number | undefined {
  return hitungUsia(parseTanggalLahir(tanggalLahir));
}
