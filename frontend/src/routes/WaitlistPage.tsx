import { Waitlist } from '@clerk/clerk-react'
import { Navigate } from 'react-router-dom'

import { DEV_NO_AUTH } from '../lib/auth-context.ts'

/**
 * In-app waitlist at `/waitlist`.
 *
 * Left to itself Clerk sends people to the hosted Account Portal
 * (`accounts.wishly.dev/waitlist`), which is styled from the Clerk dashboard
 * and so rendered as the stock purple card. Mounting the component here puts
 * it inside `<ThemedClerkProvider>`, so it picks up the same appearance — and
 * the same `.auth-page` frame — as `/sign-in` and `/sign-up`.
 *
 * `afterJoinWaitlistUrl` is deliberately unset: joining does not sign anyone
 * in, so the card should stay put and show its own confirmation.
 */
export default function WaitlistPage() {
  // Dev bypass: no Clerk instance to join a waitlist on; go straight to the app.
  if (DEV_NO_AUTH) {
    return <Navigate to="/app" replace />
  }

  return (
    <div className="auth-page">
      <Waitlist signInUrl="/sign-in" />
    </div>
  )
}
