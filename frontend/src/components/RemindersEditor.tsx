import { useState } from 'react'

import { REMINDER_PRESETS } from '../lib/validation.ts'

type RemindersEditorProps = {
  value: number[]
  onChange: (days: number[]) => void
  error?: string | null
}

const MAX_DAYS = 365

/** "7 days before" / "1 day before" / "On the day" — the checkbox label for a lead time. */
function checkLabel(days: number): string {
  if (days === 0) return 'On the day'
  return `${days} day${days === 1 ? '' : 's'} before`
}

/**
 * Lead-time picker. Every option — preset or custom — is a single checkbox,
 * so the selection lives in one place instead of being mirrored in a list.
 */
export default function RemindersEditor({ value, onChange, error }: RemindersEditorProps) {
  const [customDay, setCustomDay] = useState('')

  // Presets plus anything custom already chosen. Furthest out first; "Day of" last.
  const options = [...new Set([...REMINDER_PRESETS.map((p) => p.days), ...value])].sort(
    (a, b) => b - a
  )

  function toggle(days: number) {
    onChange(value.includes(days) ? value.filter((d) => d !== days) : [...value, days])
  }

  function addCustom() {
    const parsed = Number(customDay)
    if (!Number.isInteger(parsed) || parsed < 0 || parsed > MAX_DAYS) return
    if (!value.includes(parsed)) onChange([...value, parsed])
    setCustomDay('')
  }

  return (
    <fieldset className="groupbox reminders-editor">
      <legend>E-mail me</legend>
      <p className="field-hint">How many days before the date. Choose as many as you like.</p>

      <div className="reminder-presets">
        {options.map((days) => (
          <label key={days} className="check">
            <input type="checkbox" checked={value.includes(days)} onChange={() => toggle(days)} />
            <span>{checkLabel(days)}</span>
          </label>
        ))}
      </div>

      <div className="row">
        <label htmlFor="custom-lead-time">Other:</label>
        <input
          id="custom-lead-time"
          className="text text-short"
          type="number"
          min={0}
          max={MAX_DAYS}
          value={customDay}
          onChange={(e) => setCustomDay(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addCustom()
            }
          }}
        />
        <span>day(s) before</span>
        <button
          type="button"
          className="btn"
          onClick={addCustom}
          disabled={customDay.trim() === ''}
        >
          Add
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}
    </fieldset>
  )
}
