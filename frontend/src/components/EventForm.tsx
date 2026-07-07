import { useState } from 'react'
import type { FormEvent } from 'react'

import type { Event, EventType } from '../lib/api.ts'
import {
  DEFAULT_REMINDERS,
  EVENT_TYPES,
  MONTH_NAMES,
  validateEventYear,
  validateMonthDay,
  validateReminders,
  validateTitle,
} from '../lib/validation.ts'
import RemindersEditor from './RemindersEditor.tsx'

export type EventFormValues = {
  title: string
  event_type: EventType
  event_month: number
  event_day: number
  event_year: string
  message: string
  is_active: boolean
  reminders: number[]
}

type EventFormProps = {
  initial?: Event | null
  onSubmit: (values: EventFormValues) => Promise<void>
  onCancel: () => void
  isSubmitting: boolean
}

function emptyForm(): EventFormValues {
  return {
    title: '',
    event_type: 'birthday',
    event_month: 1,
    event_day: 1,
    event_year: '',
    message: '',
    is_active: true,
    reminders: [...DEFAULT_REMINDERS],
  }
}

function fromEvent(event: Event): EventFormValues {
  return {
    title: event.title,
    event_type: event.event_type,
    event_month: event.event_month,
    event_day: event.event_day,
    event_year: event.event_year ? String(event.event_year) : '',
    message: event.message ?? '',
    is_active: event.is_active,
    reminders: event.reminders.length > 0 ? [...event.reminders] : [...DEFAULT_REMINDERS],
  }
}

export default function EventForm({ initial, onSubmit, onCancel, isSubmitting }: EventFormProps) {
  const [values, setValues] = useState<EventFormValues>(() =>
    initial ? fromEvent(initial) : emptyForm()
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  const maxDay = values.event_month === 2 ? 29 : new Date(2024, values.event_month, 0).getDate()
  const dayOptions = Array.from({ length: maxDay }, (_, i) => i + 1)

  function setField<K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }

  function validate(): boolean {
    const next: Record<string, string> = {}
    const titleErr = validateTitle(values.title)
    if (titleErr) next.title = titleErr

    const dateErr = validateMonthDay(values.event_month, values.event_day)
    if (dateErr) next.date = dateErr

    const yearErr = validateEventYear(values.event_year)
    if (yearErr) next.event_year = yearErr

    const remindersErr = validateReminders(values.reminders)
    if (remindersErr) next.reminders = remindersErr

    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitError(null)
    if (!validate()) return

    try {
      await onSubmit(values)
    } catch {
      setSubmitError('Could not save this event. Please try again.')
    }
  }

  return (
    <form className="event-form" onSubmit={(e) => void handleSubmit(e)}>
      <h2 id="event-form-title">{initial ? 'Edit event' : 'Add an occasion'}</h2>

      <label>
        Title
        <input
          type="text"
          value={values.title}
          onChange={(e) => setField('title', e.target.value)}
          placeholder="Mom's birthday"
          required
        />
        {errors.title && <span className="form-error">{errors.title}</span>}
      </label>

      <fieldset className="type-picker">
        <legend>Type</legend>
        <div className="segmented" role="group" aria-label="Event type">
          {EVENT_TYPES.map((type) => (
            <button
              key={type.value}
              type="button"
              className={values.event_type === type.value ? 'segment segment-active' : 'segment'}
              aria-pressed={values.event_type === type.value}
              onClick={() => setField('event_type', type.value as EventType)}
            >
              {type.label}
            </button>
          ))}
        </div>
        <span className="field-hint">Chooses the email template for reminders.</span>
      </fieldset>

      <div className="date-row">
        <label>
          Month
          <select
            value={values.event_month}
            onChange={(e) => {
              const month = Number(e.target.value)
              setField('event_month', month)
              const max = month === 2 ? 29 : new Date(2024, month, 0).getDate()
              if (values.event_day > max) setField('event_day', max)
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
          <select
            value={values.event_day}
            onChange={(e) => setField('event_day', Number(e.target.value))}
          >
            {dayOptions.map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </label>

        <label>
          Year <span className="optional">(optional)</span>
          <input
            type="number"
            min={1}
            max={9999}
            placeholder="e.g. 1990"
            value={values.event_year}
            onChange={(e) => setField('event_year', e.target.value)}
          />
          {errors.event_year && <span className="form-error">{errors.event_year}</span>}
        </label>
      </div>
      {errors.date && <p className="form-error">{errors.date}</p>}

      <label>
        Personal note <span className="optional">(optional)</span>
        <textarea
          rows={3}
          value={values.message}
          onChange={(e) => setField('message', e.target.value)}
          placeholder="Gift ideas, inside jokes, anything to jog your memory…"
          maxLength={2000}
        />
      </label>

      <RemindersEditor
        value={values.reminders}
        onChange={(reminders) => setField('reminders', reminders)}
        error={errors.reminders}
      />

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={values.is_active}
          onChange={(e) => setField('is_active', e.target.checked)}
        />
        Send reminders for this event
      </label>

      {submitError && <p className="form-error">{submitError}</p>}

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : initial ? 'Save changes' : 'Add event'}
        </button>
      </div>
    </form>
  )
}
