import { Navigate, Outlet } from 'react-router-dom'

import { useMe } from '../lib/hooks.ts'
import { isOnboardingDone } from '../lib/onboarding.ts'

/**
 * Redirects first-time users to onboarding after ``GET /me`` succeeds.
 * Skips the redirect once onboarding has been completed on this browser.
 */
export default function OnboardingGate() {
  const { data: user, isLoading, isError } = useMe()

  if (isLoading) {
    return null
  }

  if (isError || !user) {
    return <p className="form-error">Could not load your profile. Please refresh.</p>
  }

  if (!isOnboardingDone(user.id)) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
