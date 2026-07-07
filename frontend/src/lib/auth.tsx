/**
 * Auth providers — the component half of the auth abstraction.
 *
 * Two implementations, chosen once at the top of the tree (main.tsx):
 *  - **Clerk** (default / production): bridges Clerk's hooks into context.
 *  - **Dev bypass** (`VITE_DEV_NO_AUTH=true`): a fixed local user, no Clerk —
 *    pair with the backend's `AUTH_DEV_BYPASS` to test the UI without Clerk.
 *
 * Components consume `useWishlyAuth()` / `useWishlyUser()` (from auth-context)
 * and never import `@clerk/clerk-react`, so the dev path renders no Clerk
 * components at all.
 */

import { useMemo, type ReactNode } from 'react'
import { useAuth, useUser, UserButton } from '@clerk/clerk-react'

import {
  AuthContext,
  DEV_NO_AUTH,
  UserContext,
  type WishlyAuth,
  type WishlyUser,
} from './auth-context.ts'

/** Bridges Clerk's hooks into our context. Must render inside <ClerkProvider>. */
function ClerkAuthBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const { user } = useUser()

  const auth = useMemo<WishlyAuth>(
    () => ({ isLoaded, isSignedIn: Boolean(isSignedIn), getToken: () => getToken() }),
    [isLoaded, isSignedIn, getToken]
  )
  const wishlyUser = useMemo<WishlyUser>(
    () => ({ firstName: user?.firstName ?? null }),
    [user?.firstName]
  )

  return (
    <AuthContext.Provider value={auth}>
      <UserContext.Provider value={wishlyUser}>{children}</UserContext.Provider>
    </AuthContext.Provider>
  )
}

/** Fixed, always-signed-in dev user. Renders no Clerk components. */
function DevAuthProvider({ children }: { children: ReactNode }) {
  const auth: WishlyAuth = {
    isLoaded: true,
    isSignedIn: true,
    // The backend dev bypass ignores the token; send a marker for clarity.
    getToken: async () => 'dev-no-auth',
  }
  return (
    <AuthContext.Provider value={auth}>
      <UserContext.Provider value={{ firstName: 'Dev' }}>{children}</UserContext.Provider>
    </AuthContext.Provider>
  )
}

/** Pick the provider for the current mode. */
export function AuthProvider({ children }: { children: ReactNode }) {
  return DEV_NO_AUTH ? (
    <DevAuthProvider>{children}</DevAuthProvider>
  ) : (
    <ClerkAuthBridge>{children}</ClerkAuthBridge>
  )
}

/** Account control in the header: Clerk's UserButton, or a dev badge. */
export function AuthUserButton() {
  if (DEV_NO_AUTH) {
    return <span className="dev-user-badge">Dev User</span>
  }
  return <UserButton afterSignOutUrl="/sign-in" />
}
