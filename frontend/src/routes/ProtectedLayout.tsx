import { Link, Navigate, NavLink, Outlet } from 'react-router-dom'

import { AuthUserButton } from '../lib/auth.tsx'
import { useWishlyAuth } from '../lib/auth-context.ts'

/**
 * Wraps all authenticated routes.
 * - Unauthenticated visitors are redirected to /sign-in.
 * - Authenticated users see the app shell with a nav bar and <Outlet />.
 */
export default function ProtectedLayout() {
  const { isLoaded, isSignedIn } = useWishlyAuth()

  // While Clerk is initialising, render nothing to avoid a flash of redirect.
  if (!isLoaded) {
    return null
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/app" className="wordmark">
          wishly<span className="wordmark-dot">.</span>
        </Link>
        <nav className="app-nav">
          <NavLink to="/app" end>
            Occasions
          </NavLink>
          <NavLink to="/app/history">History</NavLink>
          <NavLink to="/app/account">Account</NavLink>
          <AuthUserButton />
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
