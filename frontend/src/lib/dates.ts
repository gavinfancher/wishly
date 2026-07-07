/**
 * Date helpers for the UI: next occurrence and countdowns.
 *
 * Display-only — the backend owns the real send logic. Mirrors its rules:
 * Feb 29 events are observed on Feb 28 in non-leap years.
 */

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

function occurrenceInYear(year: number, month: number, day: number): Date {
  if (month === 2 && day === 29 && !isLeapYear(year)) {
    return new Date(year, 1, 28)
  }
  return new Date(year, month - 1, day)
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** The next date (today or later) on which this month/day occurs. */
export function nextOccurrence(month: number, day: number, from: Date = new Date()): Date {
  const today = startOfDay(from)
  const thisYear = occurrenceInYear(today.getFullYear(), month, day)
  if (thisYear >= today) return thisYear
  return occurrenceInYear(today.getFullYear() + 1, month, day)
}

/** Whole days from `from` until the next occurrence (0 = today). */
export function daysUntil(month: number, day: number, from: Date = new Date()): number {
  const today = startOfDay(from)
  const next = nextOccurrence(month, day, from)
  return Math.round((next.getTime() - today.getTime()) / 86_400_000)
}

/** Human countdown: "Today", "Tomorrow", "In 12 days". */
export function countdownLabel(days: number): string {
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return `In ${days} days`
}

/** Years since the origin year at the next occurrence (e.g. the age they turn). */
export function yearsAtNext(
  eventYear: number | null,
  month: number,
  day: number,
  from: Date = new Date()
): number | null {
  if (!eventYear) return null
  const next = nextOccurrence(month, day, from)
  const years = next.getFullYear() - eventYear
  return years > 0 ? years : null
}

const MONTH_ABBR = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const

export function monthAbbr(month: number): string {
  return MONTH_ABBR[month - 1] ?? String(month)
}
