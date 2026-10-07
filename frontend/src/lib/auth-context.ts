/**
 * Auth context, hooks, and mode flag (the non-component half of the auth
 * layer; see auth.tsx for the providers). Kept JSX-free so Fast Refresh stays
 * happy and components import hooks/constants from here.
 */

import { createContext, useContext } from 'react'

/** Build-time constant: when true, skip sign-in entirely (local mock mode only). */
export const DEV_NO_AUTH = import.meta.env.VITE_DEV_NO_AUTH === 'true'

export type WishlyAuth = {
  /** False only while the provider is starting up. */
  isLoaded: boolean
  isSignedIn: boolean
  /** The session token to send as a Bearer token, or null when signed out. */
  getToken: () => Promise<string | null>
  /** Both throw ApiError on failure (e.g. 401 wrong password, 409 email taken). */
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  /** Ends the session on the server (best effort) and forgets the token. */
  signOut: () => Promise<void>
}

export const AuthContext = createContext<WishlyAuth | null>(null)

export function useWishlyAuth(): WishlyAuth {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useWishlyAuth must be used within an auth provider')
  }
  return ctx
}
