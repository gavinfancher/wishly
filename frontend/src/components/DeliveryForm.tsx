import { useState } from 'react'
import type { FormEvent } from 'react'

import { useUpdateMe } from '../lib/hooks.ts'
import { timezoneOptions } from '../lib/timezones.ts'

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour)

type DeliveryFormProps = {
  initialTimezone: string
  initialSendHour: number
  submitLabel?: string
  onSaved?: () => void
}

/**
 * Timezone + send-hour form (PATCH /me), shared by the Account page and the
 * email-linked preferences page.
 */
export default function DeliveryForm({
  initialTimezone,
  initialSendHour,
  submitLabel = 'Save delivery time',
  onSaved,
}: DeliveryFormProps) {
  const updateMe = useUpdateMe()

  const [timezone, setTimezone] = useState(initialTimezone)
  const [sendHour, setSendHour] = useState(initialSendHour)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    try {
      await updateMe.mutateAsync({ timezone, send_hour: sendHour })
      setSaved(true)
      onSaved?.()
    } catch {
      setError('Could not save delivery preferences.')
    }
  }

  return (
    <form className="preferences-form" onSubmit={(e) => void handleSubmit(e)}>
      <label>
        Timezone
        <select
          value={timezone}
          onChange={(e) => {
            setTimezone(e.target.value)
            setSaved(false)
          }}
          required
        >
          {timezoneOptions(timezone).map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </label>
      <label>
        Send hour (local)
        <select
          value={sendHour}
          onChange={(e) => {
            setSendHour(Number(e.target.value))
            setSaved(false)
          }}
        >
          {HOUR_OPTIONS.map((hour) => (
            <option key={hour} value={hour}>
              {hour.toString().padStart(2, '0')}:00
            </option>
          ))}
        </select>
      </label>
      {error && <p className="form-error">{error}</p>}
      {saved && <p className="form-success">Preferences saved.</p>}
      <button type="submit" className="btn-primary" disabled={updateMe.isPending}>
        {updateMe.isPending ? 'Saving…' : submitLabel}
      </button>
    </form>
  )
}
