import DeliveryForm from '../components/DeliveryForm.tsx'
import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { errorDetail } from '../lib/api.ts'
import { useMe, useSendTestEmail } from '../lib/hooks.ts'

/** Account: who you're signed in as, and when reminder emails arrive. */
export default function AccountPage() {
  const { data: profile, isLoading, isError } = useMe()
  const sendTestEmail = useSendTestEmail()

  if (isLoading) {
    return <p className="events-status">Loading your account…</p>
  }

  if (isError || !profile) {
    return <p className="events-status">Could not load your account. Please refresh.</p>
  }

  return (
    <div className="account-page">
      <section className="panel">
        <h2>Signed in as</h2>
        <p>
          <strong>{profile.email}</strong>
        </p>
        <p className="field-hint">
          {DEV_NO_AUTH
            ? 'Running as the local dev user.'
            : 'The email you signed up with. Reminders are sent here.'}
        </p>
      </section>

      <section className="panel">
        <h2>Delivery</h2>
        <p className="panel-sub">When reminder emails arrive, for every reminder.</p>
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
            <span className="form-error">
              Could not send it
              {errorDetail(sendTestEmail.error) ? `: ${errorDetail(sendTestEmail.error)}` : ''}.
            </span>
          )}
        </div>
      </section>
    </div>
  )
}
