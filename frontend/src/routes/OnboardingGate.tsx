import { Navigate, Outlet } from 'react-router-dom'

import ServiceUnavailable from '../components/ServiceUnavailable.tsx'
import { isOffline } from '../lib/api.ts'
import { useMe } from '../lib/hooks.ts'

/**
 * Redirects first-time users to onboarding after ``GET /me`` succeeds.
 * Completion is recorded on the user row, so it follows the account across
 * browsers and devices.
 */
export default function OnboardingGate() {
  const { data: user, isLoading, isError, error } = useMe()

  if (isLoading) {
    return null
  }

  // Unreachable backend is its own state: "refresh" is useless advice while the
  // host is down, and the failure has nothing to do with the user's profile.
  if (isOffline(error)) {
    return <ServiceUnavailable />
  }

  if (isError || !user) {
    return <p className="form-error">Could not load your profile. Please refresh.</p>
  }

  // Server-side flag, not browser storage: onboarding belongs to the account, so
  // a new browser, a private window, or cleared storage must not replay it.
  if (user.onboarded_at === null) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
