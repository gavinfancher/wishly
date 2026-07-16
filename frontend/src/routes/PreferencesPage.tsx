import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import ConfirmDialog from '../components/ConfirmDialog.tsx'
import DeliveryForm from '../components/DeliveryForm.tsx'
import { useWishlyAuth } from '../lib/auth-context.ts'
import { useEvents, useMe, useUpdateEvent } from '../lib/hooks.ts'

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
  const updateEvent = useUpdateEvent()

  const [confirmPauseAll, setConfirmPauseAll] = useState(false)
  const [pausingAll, setPausingAll] = useState(false)

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

  const activeCount = events?.filter((e) => e.is_active).length ?? 0

  async function toggleEventActive(eventId: string, isActive: boolean) {
    await updateEvent.mutateAsync({ id: eventId, body: { is_active: !isActive } })
  }

  async function handlePauseAllConfirmed() {
    const active = (events ?? []).filter((e) => e.is_active)
    if (active.length === 0) return
    setPausingAll(true)
    try {
      await Promise.all(
        active.map((event) => updateEvent.mutateAsync({ id: event.id, body: { is_active: false } }))
      )
      setConfirmPauseAll(false)
    } finally {
      setPausingAll(false)
    }
  }

  return (
    <div className="preferences-page">
      <h1>Reminder preferences</h1>
      <p className="text-muted">Control when emails arrive and which occasions are active.</p>

      <section className="panel">
        <h2>Delivery time</h2>
        {profile && (
          <DeliveryForm initialTimezone={profile.timezone} initialSendHour={profile.send_hour} />
        )}
      </section>

      <section className="panel">
        <div className="preferences-section-header">
          <h2>Your occasions</h2>
          {activeCount > 0 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setConfirmPauseAll(true)}
            >
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

      {confirmPauseAll && (
        <ConfirmDialog
          title={`Pause all ${activeCount} active occasion${activeCount === 1 ? '' : 's'}?`}
          body="No reminder emails will be sent until you resume them. Nothing is deleted."
          confirmLabel="Pause all"
          isBusy={pausingAll}
          onConfirm={() => void handlePauseAllConfirmed()}
          onCancel={() => setConfirmPauseAll(false)}
        />
      )}
    </div>
  )
}
