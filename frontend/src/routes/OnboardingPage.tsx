import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Icon, Window } from '../components/Win98.tsx'
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
    <div className="veil">
      <Window title="Wishly Setup" icon="wishly" dialog="dialog" className="dialog wizard">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="wizard-body">
            <div className="wizard-art" aria-hidden="true">
              <Icon name="wishly" size={64} />
            </div>
            <div className="wizard-main">
              <h1>When should reminders land?</h1>
              <p>One e-mail per reminder, at the hour you pick. You can change it any time.</p>

              <label className="field-row">
                <span>Time zone:</span>
                <select
                  className="select"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  required
                >
                  {timezoneOptions(timezone).map((zone) => (
                    <option key={zone} value={zone}>
                      {zone}
                    </option>
                  ))}
                </select>
              </label>
              <p className="field-hint">Detected from your browser — adjust it if it’s wrong.</p>

              <label className="field-row">
                <span>Send at:</span>
                <select
                  className="select select-short"
                  value={sendHour}
                  onChange={(e) => setSendHour(Number(e.target.value))}
                >
                  {HOUR_OPTIONS.map((hour) => (
                    <option key={hour} value={hour}>
                      {hour.toString().padStart(2, '0')}:00
                    </option>
                  ))}
                </select>
                <span className="field-hint">local time</span>
              </label>

              {error && <p className="form-error">{error}</p>}
            </div>
          </div>

          <div className="wizard-actions">
            <button type="button" className="btn" disabled>
              &lt; Back
            </button>
            <button type="submit" className="btn btn-default" disabled={updateMe.isPending}>
              {updateMe.isPending ? 'Saving…' : 'Finish'}
            </button>
          </div>
        </form>
      </Window>
    </div>
  )
}
