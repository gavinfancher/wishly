import { Navigate, Outlet } from 'react-router-dom'

import { TitleBar } from '../components/Win98.tsx'
import { useWishlyAuth } from '../lib/auth-context.ts'

/**
 * Wraps all authenticated routes.
 * - Unauthenticated visitors are redirected to /sign-in.
 * - Authenticated users get the Wishly application window; the page inside
 *   supplies its menu bar, toolbar, contents and status bar.
 */
export default function ProtectedLayout() {
  const { isLoaded, isSignedIn } = useWishlyAuth()

  // While auth is initialising, render nothing to avoid a flash of redirect.
  if (!isLoaded) {
    return null
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }

  return (
    <div className="screen">
      <main className="window app-window" aria-label="Wishly">
        <TitleBar title="Wishly" icon="wishly" themeToggle />
        <div className="app-content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
