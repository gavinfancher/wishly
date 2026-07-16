import { useState } from 'react'

import ConfirmDialog from '../components/ConfirmDialog.tsx'
import DeliveryForm from '../components/DeliveryForm.tsx'
import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { useDeleteEvent, useEvents, useMe, useSendTestEmail } from '../lib/hooks.ts'

function initialFrom(name: string | null, email: string): string {
  return (name?.trim()[0] ?? email[0] ?? '?').toUpperCase()
}

function memberSince(createdAt: string): string {
  const date = new Date(createdAt)
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

/**
 * Account settings: profile identity, delivery preferences, and the
 * danger zone (remove all tracked occasions).
 */
export default function AccountPage() {
  const { data: profile, isLoading, isError } = useMe()
  const { data: events } = useEvents()
  const deleteEvent = useDeleteEvent()
  const sendTestEmail = useSendTestEmail()

  const [confirmWipe, setConfirmWipe] = useState(false)
  const [wiping, setWiping] = useState(false)
  const [wipeError, setWipeError] = useState<string | null>(null)

  if (isLoading) {
    return <p className="events-status">Loading your account…</p>
  }

  if (isError || !profile) {
    return <p className="events-status">Could not load your account. Please refresh.</p>
  }

  const fullName =
    [profile.first_name, profile.last_name].filter(Boolean).join(' ') || 'No name set'
  const eventCount = events?.length ?? 0

  async function handleWipeConfirmed() {
    if (!events?.length) return
    setWiping(true)
    setWipeError(null)
    try {
      for (const event of events) {
        await deleteEvent.mutateAsync(event.id)
      }
      setConfirmWipe(false)
    } catch {
      setWipeError('Could not remove every occasion. Some may remain — try again.')
    } finally {
      setWiping(false)
    }
  }

  return (
    <div className="account-page">
      <h1>Account</h1>
      <p className="text-muted">Your profile, delivery preferences, and data.</p>

      <section className="panel">
        <h2>Profile</h2>
        <div className="profile-row">
          <span className="profile-initial" aria-hidden="true">
            {initialFrom(profile.first_name, profile.email)}
          </span>
          <div className="profile-details">
            <strong>{fullName}</strong>
            <span className="text-muted">{profile.email}</span>
            <span className="text-muted">Member since {memberSince(profile.created_at)}</span>
          </div>
        </div>
        <p className="field-hint">
          {DEV_NO_AUTH
            ? 'Running as the local dev user — name and email are fixed.'
            : 'Name and email come from your sign-in account. Change them from the account menu in the header.'}
        </p>
      </section>

      <section className="panel">
        <h2>Delivery</h2>
        <p className="panel-sub">
          When reminder emails arrive. Applies to every occasion you track.
        </p>
        <DeliveryForm initialTimezone={profile.timezone} initialSendHour={profile.send_hour} />
        <div className="test-email-row">
          <button
            type="button"
            className="btn-secondary"
            disabled={sendTestEmail.isPending}
            onClick={() => sendTestEmail.mutate()}
          >
            {sendTestEmail.isPending ? 'Sending…' : 'Send a test reminder'}
          </button>
          {sendTestEmail.isSuccess && (
            <span className="form-success">On its way to {profile.email}.</span>
          )}
          {sendTestEmail.isError && (
            <span className="form-error">Could not send the test email. Try again.</span>
          )}
        </div>
      </section>

      <section className="panel panel-danger">
        <h2>Danger zone</h2>
        <div className="danger-row">
          <div>
            <strong>Remove all occasions</strong>
            <p className="text-muted">
              {eventCount === 0
                ? 'Nothing tracked right now.'
                : `Deletes all ${eventCount} occasion${eventCount === 1 ? '' : 's'} and their reminder schedules.`}
            </p>
          </div>
          <button
            type="button"
            className="btn-danger"
            disabled={eventCount === 0 || wiping}
            onClick={() => setConfirmWipe(true)}
          >
            Remove all
          </button>
        </div>
        {wipeError && <p className="form-error">{wipeError}</p>}
        <p className="field-hint">
          Deleting the account itself happens where you sign in — removing your occasions here stops
          all reminders.
        </p>
      </section>

      {confirmWipe && (
        <ConfirmDialog
          title={`Remove all ${eventCount} occasion${eventCount === 1 ? '' : 's'}?`}
          body="Every tracked date and its reminder schedule will be deleted. This cannot be undone."
          confirmLabel="Remove everything"
          danger
          isBusy={wiping}
          onConfirm={() => void handleWipeConfirmed()}
          onCancel={() => setConfirmWipe(false)}
        />
      )}
    </div>
  )
}
