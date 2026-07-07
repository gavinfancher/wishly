/**
 * Client-side validation mirroring backend schemas (T3.1 / T6.4).
 * Feb 29 is always allowed; the sender observes it on Feb 28 in non-leap years.
 */

import type { EventType } from './api.ts'

const MAX_DAY_IN_MONTH = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] as const

export const EVENT_TYPES: { value: EventType; label: string }[] = [
  { value: 'birthday', label: 'Birthday' },
  { value: 'anniversary', label: 'Anniversary' },
  { value: 'custom', label: 'Custom' },
]

export const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const

export const DEFAULT_REMINDERS = [30, 7, 1, 0]

export const REMINDER_PRESETS = [
  { days: 30, label: '30 days' },
  { days: 7, label: '7 days' },
  { days: 1, label: '1 day' },
  { days: 0, label: 'Day of' },
] as const

export function validateTitle(title: string): string | null {
  const trimmed = title.trim()
  if (!trimmed) return 'Title is required.'
  if (trimmed.length > 200) return 'Title must be 200 characters or fewer.'
  return null
}

export function validateMonthDay(month: number, day: number): string | null {
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    return 'Month must be between 1 and 12.'
  }
  const maxDay = MAX_DAY_IN_MONTH[month]
  if (!Number.isInteger(day) || day < 1 || day > maxDay) {
    return `Day must be between 1 and ${maxDay} for this month.`
  }
  return null
}

export function validateEventYear(year: string): string | null {
  if (!year.trim()) return null
  const parsed = Number(year)
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 9999) {
    return 'Year must be between 1 and 9999.'
  }
  return null
}

export function validateReminders(days: number[]): string | null {
  if (days.length === 0) return 'Add at least one reminder lead time.'
  const seen = new Set<number>()
  for (const day of days) {
    if (!Number.isInteger(day) || day < 0 || day > 365) {
      return 'Each reminder must be between 0 and 365 days before.'
    }
    if (seen.has(day)) return 'Reminder lead times must be unique.'
    seen.add(day)
  }
  return null
}

export function formatEventDate(month: number, day: number, year: number | null): string {
  const monthName = MONTH_NAMES[month - 1] ?? String(month)
  if (year) return `${monthName} ${day}, ${year}`
  return `${monthName} ${day}`
}

export function formatReminderLabel(days: number): string {
  if (days === 0) return 'Day of'
  if (days === 1) return '1 day before'
  return `${days} days before`
}
