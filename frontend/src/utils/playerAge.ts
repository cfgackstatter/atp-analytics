/** ATP bio birthdates are stored as YYYY/MM/DD; ranking dates as YYYY-MM-DD. */

export function parsePlayerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const normalized = value.trim().replace(/\//g, '-');
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(normalized);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return date;
}

export function hasBirthdate(birthdate: string | null | undefined): boolean {
  return parsePlayerDate(birthdate) !== null;
}

/** Fractional age in years at a ranking/calendar date. */
export function ageAtDate(
  birthdate: string | null | undefined,
  atDate: string | null | undefined
): number | null {
  const born = parsePlayerDate(birthdate);
  const at = parsePlayerDate(atDate);
  if (!born || !at) return null;
  const ms = at.getTime() - born.getTime();
  if (ms < 0) return null;
  return ms / (365.25 * 24 * 60 * 60 * 1000);
}

export function formatAge(age: number): string {
  return age.toFixed(1);
}
