import { useState } from 'react'

import { REMINDER_PRESETS } from '../lib/validation.ts'

type RemindersEditorProps = {
  value: number[]
  onChange: (days: number[]) => void
  error?: string | null
}

const MAX_DAYS = 365

/** "7 days" / "1 day" / "Day of" — the chip face for a lead time. */
function chipLabel(days: number): string {
  if (days === 0) return 'Day of'
  return `${days} day${days === 1 ? '' : 's'}`
}

/**
 * Lead-time picker. Every option — preset or custom — is a single toggle chip,
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
    <fieldset className="reminders-editor">
      <legend>Reminder lead times</legend>
      <p className="field-hint">Pick when the emails go out. Choose as many as you like.</p>

      <div className="reminder-presets">
        {options.map((days) => (
          <button
            key={days}
            type="button"
            className={`chip ${value.includes(days) ? 'chip-active' : ''}`}
            aria-pressed={value.includes(days)}
            onClick={() => toggle(days)}
          >
            {chipLabel(days)}
          </button>
        ))}
      </div>

      <div className="reminder-custom">
        <label className="reminder-custom-label" htmlFor="custom-lead-time">
          Another lead time
        </label>
        <div className="reminder-custom-row">
          <input
            id="custom-lead-time"
            type="number"
            min={0}
            max={MAX_DAYS}
            placeholder="days"
            value={customDay}
            onChange={(e) => setCustomDay(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addCustom()
              }
            }}
          />
          <button
            type="button"
            className="btn-secondary btn-compact"
            onClick={addCustom}
            disabled={customDay.trim() === ''}
          >
            Add
          </button>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}
    </fieldset>
  )
}
