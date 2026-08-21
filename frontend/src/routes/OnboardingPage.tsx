import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useUpdateMe } from '../lib/hooks.ts'
import { timezoneOptions } from '../lib/timezones.ts'

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour)

/**
 * First-run capture of timezone and preferred send hour (T6.3).
 * Defaults timezone to the browser's IANA zone and send hour to 8.
 */
export default function OnboardingPage() {
  const navigate = useNavigate()
  const updateMe = useUpdateMe()

  const defaultTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  const [timezone, setTimezone] = useState(defaultTimezone)
  const [sendHour, setSendHour] = useState(8)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    try {
      // `onboarded` stamps users.onboarded_at server-side, so completion follows
      // the account rather than this browser's localStorage.
      await updateMe.mutateAsync({ timezone, send_hour: sendHour, onboarded: true })
      navigate('/app', { replace: true })
    } catch {
      setError('Could not save your preferences. Please try again.')
    }
  }

  return (
    <div className="onboarding">
      <form onSubmit={(e) => void handleSubmit(e)} className="form-panel">
        <div className="form-panel-head">
          <h1>When should reminders land?</h1>
          <p className="form-panel-sub">
            One email per reminder, at the hour you pick. Change it any time.
          </p>
        </div>

        <div className="form-panel-body">
          <label className="field">
            <span className="field-label">Timezone</span>
            <select value={timezone} onChange={(e) => setTimezone(e.target.value)} required>
              {timezoneOptions(timezone).map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
            <span className="field-hint">Detected from your browser — adjust if it’s wrong.</span>
          </label>

          <label className="field">
            <span className="field-label">Delivery hour (local time)</span>
            <select value={sendHour} onChange={(e) => setSendHour(Number(e.target.value))}>
              {HOUR_OPTIONS.map((hour) => (
                <option key={hour} value={hour}>
                  {hour.toString().padStart(2, '0')}:00
                </option>
              ))}
            </select>
          </label>

          {error && <p className="form-error">{error}</p>}
        </div>

        <div className="form-panel-actions">
          <button type="submit" className="btn-primary btn-compact" disabled={updateMe.isPending}>
            {updateMe.isPending ? 'Saving…' : 'Save and continue'}
          </button>
        </div>
      </form>
    </div>
  )
}
