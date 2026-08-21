import { SignIn } from '@clerk/clerk-react'
import { Navigate, useSearchParams } from 'react-router-dom'

import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { clerkAppearance } from '../lib/clerk-appearance.ts'
import { DASHBOARD_URL } from '../lib/urls.ts'

export default function SignInPage() {
  const [searchParams] = useSearchParams()
  const redirectUrl = searchParams.get('redirect_url') ?? DASHBOARD_URL

  // Dev bypass: already "signed in", so there is nothing to render here.
  if (DEV_NO_AUTH) {
    return <Navigate to={redirectUrl} replace />
  }

  return (
    <div className="auth-page">
      <SignIn
        appearance={clerkAppearance}
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
        fallbackRedirectUrl={redirectUrl}
        forceRedirectUrl={redirectUrl}
      />
    </div>
  )
}
