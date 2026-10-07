import { useState } from 'react'
import type { FormEvent } from 'react'

import { Icon, Window } from './Win98.tsx'
import type { User } from '../lib/api.ts'
import { useMe, useUpdateMe } from '../lib/hooks.ts'
import { timezoneOptions } from '../lib/timezones.ts'
import { useEscape } from '../lib/useEscape.ts'

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour)

/**
 * File › Time Zone…: when reminder e-mails arrive. OK saves and closes, Cancel
 * closes without saving, Apply saves and stays open (grayed out until something
 * changes).
 */
function TimeZoneForm({ profile, onClose }: { profile: User; onClose: () => void }) {
  const updateMe = useUpdateMe()

  const [timezone, setTimezone] = useState(profile.timezone)
  const [sendHour, setSendHour] = useState(profile.send_hour)
  const [error, setError] = useState<string | null>(null)

  const dirty = timezone !== profile.timezone || sendHour !== profile.send_hour
  useEscape(onClose, updateMe.isPending)

  /** Saves if anything changed. Returns false when the save failed. */
  async function apply(): Promise<boolean> {
    if (!dirty) return true
    setError(null)
    try {
      await updateMe.mutateAsync({ timezone, send_hour: sendHour })
      return true
    } catch {
      setError('Could not save delivery preferences.')
      return false
    }
  }

  async function handleOk(event: FormEvent) {
    event.preventDefault()
    if (await apply()) onClose()
  }

  return (
    <form className="body" onSubmit={(e) => void handleOk(e)}>
      <div className="account-who">
        <Icon name="clock" size={32} />
        <p>Reminder e-mails arrive at this hour, in this time zone, for every reminder.</p>
      </div>
      <label className="field-row">
        <span>Time zone:</span>
        <select
          className="select"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          required
          autoFocus
        >
          {timezoneOptions(timezone).map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </label>
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
      </label>
      {error && <p className="form-error">{error}</p>}

      <div className="row end">
        <button type="submit" className="btn btn-default" disabled={updateMe.isPending}>
          OK
        </button>
        <button type="button" className="btn" onClick={onClose} disabled={updateMe.isPending}>
          Cancel
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => void apply()}
          disabled={!dirty || updateMe.isPending}
        >
          {updateMe.isPending ? 'Saving…' : 'Apply'}
        </button>
      </div>
    </form>
  )
}

export default function TimeZoneDialog({ onClose }: { onClose: () => void }) {
  const { data: profile, isLoading } = useMe()

  return (
    <div className="veil" role="presentation">
      <Window title="Time Zone" icon="clock" dialog="dialog" className="dialog" onClose={onClose}>
        {profile ? (
          <TimeZoneForm profile={profile} onClose={onClose} />
        ) : (
          <p className="empty">
            {isLoading ? 'Loading…' : 'Could not load your settings. Please try again.'}
          </p>
        )}
      </Window>
    </div>
  )
}
