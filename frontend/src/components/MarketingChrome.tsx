import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useWishlyAuth } from '../lib/auth-context.ts'
import { DASHBOARD_URL, isExternal } from '../lib/urls.ts'

/**
 * "Log In" for the public pages: the dashboard if already signed in (a full
 * navigation when it lives on another origin), else the sign-in page.
 */
export function LoginLink({ className, children }: { className?: string; children: ReactNode }) {
  const { isLoaded, isSignedIn } = useWishlyAuth()
  const signedIn = isLoaded && isSignedIn

  if (signedIn && isExternal(DASHBOARD_URL)) {
    return (
      <a href={DASHBOARD_URL} className={className}>
        {children}
      </a>
    )
  }
  return (
    <Link to={signedIn ? DASHBOARD_URL : '/sign-in'} className={className}>
      {children}
    </Link>
  )
}
