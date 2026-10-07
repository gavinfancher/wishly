import DeliveryForm from '../components/DeliveryForm.tsx'
import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { useMe } from '../lib/hooks.ts'

/** Account: who you're signed in as, and when reminder emails arrive. */
export default function AccountPage() {
  const { data: profile, isLoading, isError } = useMe()

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
      </section>
    </div>
  )
}
