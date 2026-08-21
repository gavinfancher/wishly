import { SignUp } from '@clerk/clerk-react'
import { Navigate } from 'react-router-dom'

import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { clerkAppearance } from '../lib/clerk-appearance.ts'
import { DASHBOARD_URL } from '../lib/urls.ts'

export default function SignUpPage() {
  // Dev bypass: no Clerk sign-up; go straight to the app.
  if (DEV_NO_AUTH) {
    return <Navigate to="/app" replace />
  }

  return (
    <div className="auth-page">
      <SignUp
        appearance={clerkAppearance}
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        fallbackRedirectUrl={DASHBOARD_URL}
      />
    </div>
  )
}
