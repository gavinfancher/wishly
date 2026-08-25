import { Link } from 'react-router-dom'

import { useWishlyAuth } from '../lib/auth-context.ts'
import { DASHBOARD_URL, isExternal } from '../lib/urls.ts'

/**
 * Header and footer shared by the public pages (`/` and `/pricing`), so the two
 * agree on the wordmark, the nav, and where Login points.
 */
export function MarketingHeader() {
  const { isLoaded, isSignedIn } = useWishlyAuth()
  const signedIn = isLoaded && isSignedIn

  return (
    <header className="landing-header">
      <Link to="/" className="wordmark">
        wishly<span className="wordmark-dot">.</span>
      </Link>
      <nav className="landing-nav">
        <Link to="/pricing">Pricing</Link>
        {signedIn && isExternal(DASHBOARD_URL) ? (
          <a href={DASHBOARD_URL} className="btn-secondary">
            Login
          </a>
        ) : (
          <Link to={signedIn ? DASHBOARD_URL : '/sign-in'} className="btn-secondary">
            Login
          </Link>
        )}
      </nav>
    </header>
  )
}

export function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <span>
        wishly<span className="wordmark-dot">.</span>
      </span>
      <span>Reminders for the dates that matter.</span>
    </footer>
  )
}
