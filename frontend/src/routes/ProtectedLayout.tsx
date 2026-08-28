import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'

import { AuthUserButton } from '../lib/auth.tsx'
import { useWishlyAuth } from '../lib/auth-context.ts'

/**
 * Wraps all authenticated routes.
 * - Unauthenticated visitors are redirected to /sign-in.
 * - Authenticated users see the console shell: sidebar, topbar, content.
 */

/** Sidebar icons — 16px, currentColor, so they inherit the nav item's state. */
const iconProps = {
  width: 16,
  height: 16,
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

function IconCalendar() {
  return (
    <svg {...iconProps} aria-hidden="true">
      <rect x="2" y="3.5" width="12" height="10.5" rx="2" />
      <path d="M2 6.75h12M5.5 2v3M10.5 2v3" />
    </svg>
  )
}

function IconCalendarGrid() {
  return (
    <svg {...iconProps} aria-hidden="true">
      <rect x="2" y="3.5" width="12" height="10.5" rx="2" />
      <path d="M2 6.75h12M5.5 2v3M10.5 2v3M6.25 9.5h3.5M2 11.75h12" />
    </svg>
  )
}

function IconSent() {
  return (
    <svg {...iconProps} aria-hidden="true">
      <path d="M14 2 7 9M14 2l-4.5 12L7 9l-5-2.5L14 2Z" />
    </svg>
  )
}

function IconPerson() {
  return (
    <svg {...iconProps} aria-hidden="true">
      <circle cx="8" cy="5.5" r="2.75" />
      <path d="M2.75 14a5.25 5.25 0 0 1 10.5 0" />
    </svg>
  )
}

/** Route → section name shown in the topbar. Longest match wins. */
const SECTIONS: ReadonlyArray<readonly [string, string]> = [
  ['/app/calendar', 'Calendar'],
  ['/app/history', 'Sent reminders'],
  ['/app/account', 'Account'],
  ['/onboarding', 'Set up reminders'],
  ['/app', 'Occasions'],
]

function sectionTitle(pathname: string): string {
  return SECTIONS.find(([path]) => pathname.startsWith(path))?.[1] ?? 'Wishly'
}

export default function ProtectedLayout() {
  const { isLoaded, isSignedIn } = useWishlyAuth()
  const { pathname } = useLocation()

  // While Clerk is initialising, render nothing to avoid a flash of redirect.
  if (!isLoaded) {
    return null
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/app" className="sidebar-brand wordmark">
          wishly<span className="wordmark-dot">.</span>
        </Link>

        <nav className="sidebar-nav">
          <NavLink to="/app" end className="nav-item">
            <IconCalendar />
            <span className="nav-label">Occasions</span>
          </NavLink>
          <NavLink to="/app/calendar" className="nav-item">
            <IconCalendarGrid />
            <span className="nav-label">Calendar</span>
          </NavLink>
          <NavLink to="/app/history" className="nav-item">
            <IconSent />
            <span className="nav-label">History</span>
          </NavLink>
          <NavLink to="/app/account" className="nav-item">
            <IconPerson />
            <span className="nav-label">Account</span>
          </NavLink>
        </nav>

        <div className="sidebar-foot">
          <AuthUserButton />
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <h1>{sectionTitle(pathname)}</h1>
        </header>
        <div className="content">
          <div className="view">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  )
}
