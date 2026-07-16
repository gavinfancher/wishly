import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useUpdateMe } from '../lib/hooks.ts'
import { timezoneOptions } from '../lib/timezones.ts'
import { markOnboardingDone } from '../lib/onboarding.ts'

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
      const user = await updateMe.mutateAsync({ timezone, send_hour: sendHour })
      markOnboardingDone(user.id)
      navigate('/app', { replace: true })
    } catch {
      setError('Could not save your preferences. Please try again.')
    }
  }

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <h1>When should reminders land?</h1>
        <p className="onboarding-sub">
          One email per reminder, in your inbox at the hour you pick. You can change this any time.
        </p>

        <form onSubmit={(e) => void handleSubmit(e)} className="onboarding-form">
          <label>
            Timezone
            <select value={timezone} onChange={(e) => setTimezone(e.target.value)} required>
              {timezoneOptions(timezone).map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
            <span className="field-hint">Detected from your browser — adjust if it’s wrong.</span>
          </label>

          <label>
            Delivery hour (local time)
            <select value={sendHour} onChange={(e) => setSendHour(Number(e.target.value))}>
              {HOUR_OPTIONS.map((hour) => (
                <option key={hour} value={hour}>
                  {hour.toString().padStart(2, '0')}:00
                </option>
              ))}
            </select>
          </label>

          {error && <p className="form-error">{error}</p>}

          <button type="submit" className="btn-primary" disabled={updateMe.isPending}>
            {updateMe.isPending ? 'Saving…' : 'Save and continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
