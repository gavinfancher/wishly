import { useState } from 'react'

import { REMINDER_PRESETS } from '../lib/validation.ts'

type RemindersEditorProps = {
  value: number[]
  onChange: (days: number[]) => void
  error?: string | null
}

/** Toggle preset chips and add custom lead times (0–365 days). */
export default function RemindersEditor({ value, onChange, error }: RemindersEditorProps) {
  const [customDay, setCustomDay] = useState('')

  const sorted = [...value].sort((a, b) => b - a)

  function togglePreset(days: number) {
    if (value.includes(days)) {
      onChange(value.filter((d) => d !== days))
    } else {
      onChange([...value, days])
    }
  }

  function addCustom() {
    const parsed = Number(customDay)
    if (!Number.isInteger(parsed) || parsed < 0 || parsed > 365) return
    if (value.includes(parsed)) {
      setCustomDay('')
      return
    }
    onChange([...value, parsed])
    setCustomDay('')
  }

  function removeDay(days: number) {
    onChange(value.filter((d) => d !== days))
  }

  return (
    <fieldset className="reminders-editor">
      <legend>Reminder lead times</legend>
      <p className="field-hint">When should we email you before this occasion?</p>

      <div className="reminder-presets">
        {REMINDER_PRESETS.map((preset) => (
          <button
            key={preset.days}
            type="button"
            className={`chip ${value.includes(preset.days) ? 'chip-active' : ''}`}
            onClick={() => togglePreset(preset.days)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="reminder-custom">
        <input
          type="number"
          min={0}
          max={365}
          placeholder="Custom days"
          value={customDay}
          onChange={(e) => setCustomDay(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addCustom()
            }
          }}
        />
        <button type="button" className="btn-secondary" onClick={addCustom}>
          Add
        </button>
      </div>

      {sorted.length > 0 && (
        <ul className="reminder-list">
          {sorted.map((days) => (
            <li key={days}>
              <span>{days === 0 ? 'Day of' : `${days} day${days === 1 ? '' : 's'} before`}</span>
              <button
                type="button"
                className="btn-icon"
                aria-label={`Remove ${days} day reminder`}
                onClick={() => removeDay(days)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="form-error">{error}</p>}
    </fieldset>
  )
}
