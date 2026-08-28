/**
 * Month-rail construction for the calendar view.
 *
 * Occasions carry a month/day but no year — they recur annually — so a calendar
 * has to project them onto concrete dates before it can draw anything. That
 * projection is the whole of the interesting logic here, and it is kept pure
 * (no React, no fetching) so the year-boundary and Feb 29 cases are testable.
 *
 * Mirrors `dates.ts` on the Feb 29 rule, which in turn mirrors the backend:
 * a Feb 29 occasion is observed on Feb 28 in a non-leap year.
 */

import type { Event } from './api.ts'

export type MonthOccasion = {
  event: Event
  /** Day of the month it is observed on — 28 for a Feb 29 event in a common year. */
  day: number
  /** Whole days from today. Negative once the date is behind us. */
  daysFromToday: number
  /** True when this year's date has already passed (only possible in month one). */
  isPast: boolean
}

export type CalendarMonth = {
  /** Stable React key, e.g. `2026-09`. */
  key: string
  year: number
  /** 1-12, matching `Event.event_month`. */
  month: number
  /** e.g. `September 2026`. */
  label: string
  /**
   * Day numbers laid out in week rows, `null` for the leading/trailing padding
   * that keeps each row seven cells wide.
   */
  weeks: (number | null)[][]
  /** Every occasion falling in this month, earliest first. */
  occasions: MonthOccasion[]
}

const MS_PER_DAY = 86_400_000

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

export function daysInMonth(year: number, month: number): number {
  // Day 0 of the next month is the last day of this one.
  return new Date(year, month, 0).getDate()
}

/**
 * The day of `month` in `year` on which an occasion is observed, or `null` when
 * it does not fall in that month at all.
 */
export function observedDay(event: Event, year: number, month: number): number | null {
  if (event.event_month !== month) return null
  if (month === 2 && event.event_day === 29 && !isLeapYear(year)) return 28
  // A malformed row (day 31 in a 30-day month) would otherwise render a cell
  // that does not exist; clamp rather than drop it, so the occasion stays visible.
  return Math.min(event.event_day, daysInMonth(year, month))
}

/** Whole days between two dates, ignoring the time of day. */
export function daysBetween(from: Date, to: Date): number {
  return Math.round((startOfDay(to).getTime() - startOfDay(from).getTime()) / MS_PER_DAY)
}

/** Week rows for a month, padded with `null` so every row has seven cells. */
export function monthWeeks(year: number, month: number): (number | null)[][] {
  const total = daysInMonth(year, month)
  const leading = new Date(year, month - 1, 1).getDay() // 0 = Sunday
  const cells: (number | null)[] = [
    ...Array<null>(leading).fill(null),
    ...Array.from({ length: total }, (_, i) => i + 1),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const weeks: (number | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}

/**
 * Twelve consecutive months starting with the one containing `from`, each with
 * its grid and the occasions that land in it.
 *
 * The window starts at the *current* month rather than today, so the month you
 * are living in is drawn whole. That means an occasion earlier this month has
 * already passed — it is still listed, flagged `isPast`, because a calendar that
 * silently omitted a date it plainly contains would read as a bug.
 */
export function buildMonthRail(
  events: Event[],
  from: Date = new Date(),
  monthCount = 12
): CalendarMonth[] {
  const today = startOfDay(from)
  const months: CalendarMonth[] = []

  for (let offset = 0; offset < monthCount; offset += 1) {
    const cursor = new Date(today.getFullYear(), today.getMonth() + offset, 1)
    const year = cursor.getFullYear()
    const month = cursor.getMonth() + 1

    const occasions: MonthOccasion[] = []
    for (const event of events) {
      const day = observedDay(event, year, month)
      if (day === null) continue
      const daysFromToday = daysBetween(today, new Date(year, month - 1, day))
      occasions.push({ event, day, daysFromToday, isPast: daysFromToday < 0 })
    }
    occasions.sort((a, b) => a.day - b.day || a.event.title.localeCompare(b.event.title))

    months.push({
      key: `${year}-${String(month).padStart(2, '0')}`,
      year,
      month,
      label: cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
      weeks: monthWeeks(year, month),
      occasions,
    })
  }

  return months
}
