import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useWishlyAuth } from '../lib/auth-context.ts'
import { useEvents, useMe, useUpdateEvent, useUpdateMe } from '../lib/hooks.ts'

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour)

/** Minimal standalone shell — this page is also reached from email links. */
function PreferencesShell({ children }: { children: ReactNode }) {
  return (
    <div className="prefs-shell">
      <header className="app-header">
        <Link to="/" className="wordmark">
          wishly<span className="wordmark-dot">.</span>
        </Link>
      </header>
      <main className="app-main">{children}</main>
    </div>
  )
}

/**
 * Preferences / manage page linked from reminder emails (T6.5).
 *
 * Email links arrive as ``/preferences?u=<clerk_user_id>``. Signed-in users can
 * adjust delivery time and pause individual events.
 */
export default function PreferencesPage() {
  const { isLoaded, isSignedIn } = useWishlyAuth()
  const [searchParams] = useSearchParams()
  const linkedUserId = searchParams.get('u')

  if (!isLoaded) return null

  if (!isSignedIn) {
    return (
      <PreferencesShell>
        <div className="preferences-page">
          <h1>Manage your reminders</h1>
          <p>Sign in to update when reminders arrive or pause occasions you track.</p>
          <Link
            to={`/sign-in?redirect_url=${encodeURIComponent(window.location.pathname + window.location.search)}`}
            className="btn-primary"
          >
            Sign in
          </Link>
        </div>
      </PreferencesShell>
    )
  }

  return (
    <PreferencesShell>
      <PreferencesForm linkedUserId={linkedUserId} />
    </PreferencesShell>
  )
}

function PreferencesForm({ linkedUserId }: { linkedUserId: string | null }) {
  const { data: profile, isLoading: profileLoading } = useMe()
  const { data: events, isLoading: eventsLoading } = useEvents()
  const updateMe = useUpdateMe()
  const updateEvent = useUpdateEvent()

  const [timezone, setTimezone] = useState<string | null>(null)
  const [sendHour, setSendHour] = useState<number | null>(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeTimezone = timezone ?? profile?.timezone ?? 'UTC'
  const activeSendHour = sendHour ?? profile?.send_hour ?? 8

  if (profileLoading || eventsLoading) {
    return <p className="events-status">Loading preferences…</p>
  }

  if (linkedUserId && profile && linkedUserId !== profile.id) {
    return (
      <div className="preferences-page">
        <h1>Wrong account</h1>
        <p>
          This link is for a different Wishly account. Sign out and sign in with the email that
          receives reminders.
        </p>
        <Link to="/app" className="btn-secondary">
          Go to your dates
        </Link>
      </div>
    )
  }

  async function handleDeliverySubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaved(false)
    try {
      await updateMe.mutateAsync({ timezone: activeTimezone, send_hour: activeSendHour })
      setSaved(true)
    } catch {
      setError('Could not save delivery preferences.')
    }
  }

  async function toggleEventActive(eventId: string, isActive: boolean) {
    await updateEvent.mutateAsync({ id: eventId, body: { is_active: !isActive } })
  }

  async function pauseAll() {
    if (!events?.length) return
    const active = events.filter((e) => e.is_active)
    if (active.length === 0) return
    const confirmed = window.confirm(`Pause reminders for all ${active.length} active event(s)?`)
    if (!confirmed) return
    await Promise.all(
      active.map((event) => updateEvent.mutateAsync({ id: event.id, body: { is_active: false } }))
    )
  }

  return (
    <div className="preferences-page">
      <h1>Reminder preferences</h1>
      <p className="text-muted">Control when emails arrive and which occasions are active.</p>

      <section className="preferences-section">
        <h2>Delivery time</h2>
        <form className="preferences-form" onSubmit={(e) => void handleDeliverySubmit(e)}>
          <label>
            Timezone
            <input
              type="text"
              value={activeTimezone}
              onChange={(e) => setTimezone(e.target.value)}
              required
            />
          </label>
          <label>
            Send hour (local)
            <select value={activeSendHour} onChange={(e) => setSendHour(Number(e.target.value))}>
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
            {updateMe.isPending ? 'Saving…' : 'Save delivery time'}
          </button>
        </form>
      </section>

      <section className="preferences-section">
        <div className="preferences-section-header">
          <h2>Your occasions</h2>
          {events && events.some((e) => e.is_active) && (
            <button type="button" className="btn-secondary" onClick={() => void pauseAll()}>
              Pause all
            </button>
          )}
        </div>

        {!events?.length && <p className="text-muted">No events tracked yet.</p>}

        {events && events.length > 0 && (
          <ul className="preferences-events">
            {events.map((event) => (
              <li key={event.id}>
                <div>
                  <strong>{event.title}</strong>
                  <span className="text-muted">{event.is_active ? 'Reminders on' : 'Paused'}</span>
                </div>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={updateEvent.isPending}
                  onClick={() => void toggleEventActive(event.id, event.is_active)}
                >
                  {event.is_active ? 'Pause' : 'Resume'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link to="/app" className="preferences-back">
        ← Back to your dates
      </Link>
    </div>
  )
}
