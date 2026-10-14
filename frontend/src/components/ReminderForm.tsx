import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, isOffline } from '../lib/api.ts'
import type { Reminder, ReminderInput } from '../lib/api.ts'
import {
  DEFAULT_REMINDERS,
  MONTH_NAMES,
  validateMonthDay,
  validateReminders,
  validateTitle,
} from '../lib/validation.ts'
import RemindersEditor from './RemindersEditor.tsx'

type ReminderFormProps = {
  initial: Reminder | null
  onSubmit: (values: ReminderInput) => Promise<void>
  onCancel: () => void
  isSubmitting: boolean
}

/** Feb allows 29: the server sends on Feb 28 in non-leap years. */
function daysInMonth(month: number): number {
  return month === 2 ? 29 : new Date(2024, month, 0).getDate()
}

function describeSaveFailure(err: unknown): string {
  if (isOffline(err)) return 'Wishly is unreachable. Check your connection and try again.'
  if (err instanceof ApiError && err.status === 422) return 'Some of those details are not valid.'
  if (err instanceof ApiError && err.status === 401) return 'Your session expired. Sign in again.'
  return 'Could not save. Please try again.'
}

/** Add or edit one reminder: a name, a yearly date, and the days before it to email. */
export default function ReminderForm({
  initial,
  onSubmit,
  onCancel,
  isSubmitting,
}: ReminderFormProps) {
  const [values, setValues] = useState<ReminderInput>(
    initial
      ? {
          title: initial.title,
          month: initial.month,
          day: initial.day,
          days_before: initial.days_before,
        }
      : { title: '', month: 1, day: 1, days_before: [...DEFAULT_REMINDERS] }
  )
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof ReminderInput>(key: K, value: ReminderInput[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setError(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const body = { ...values, title: values.title.trim() }
    const problem =
      validateTitle(body.title) ??
      validateMonthDay(body.month, body.day) ??
      validateReminders(body.days_before)
    if (problem) {
      setError(problem)
      return
    }
    try {
      await onSubmit(body)
    } catch (err) {
      setError(describeSaveFailure(err))
    }
  }

  const dayOptions = Array.from({ length: daysInMonth(values.month) }, (_, i) => i + 1)

  return (
    <form className="event-form" onSubmit={(e) => void handleSubmit(e)}>
      <h2 id="reminder-form-title">{initial ? 'Edit reminder' : 'Add a reminder'}</h2>

      <label>
        What is it?
        <input
          type="text"
          value={values.title}
          onChange={(e) => set('title', e.target.value)}
          placeholder="Mom's birthday"
          maxLength={200}
          required
        />
      </label>

      <div className="date-row">
        <label>
          Month
          <select
            value={values.month}
            onChange={(e) => {
              const month = Number(e.target.value)
              set('month', month)
              if (values.day > daysInMonth(month)) set('day', daysInMonth(month))
            }}
          >
            {MONTH_NAMES.map((name, index) => (
              <option key={name} value={index + 1}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Day
          <select value={values.day} onChange={(e) => set('day', Number(e.target.value))}>
            {dayOptions.map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </label>
      </div>
      <span className="field-hint">Repeats every year.</span>

      <RemindersEditor value={values.days_before} onChange={(days) => set('days_before', days)} />

      {error && <p className="form-error">{error}</p>}

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : initial ? 'Save changes' : 'Add reminder'}
        </button>
      </div>
    </form>
  )
}
