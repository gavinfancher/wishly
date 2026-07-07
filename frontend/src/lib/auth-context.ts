/**
 * Auth context, hooks, and mode flag (the non-component half of the auth
 * abstraction; see auth.tsx for the providers). Kept JSX-free so Fast Refresh
 * stays happy and components import hooks/constants from here.
 */

import { createContext, useContext } from 'react'

/** Build-time constant: when true, skip Clerk entirely (local dev only). */
export const DEV_NO_AUTH = import.meta.env.VITE_DEV_NO_AUTH === 'true'

export type WishlyAuth = {
  isLoaded: boolean
  isSignedIn: boolean
  getToken: () => Promise<string | null>
}

export type WishlyUser = {
  firstName: string | null
}

export const AuthContext = createContext<WishlyAuth | null>(null)
export const UserContext = createContext<WishlyUser>({ firstName: null })

export function useWishlyAuth(): WishlyAuth {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useWishlyAuth must be used within an auth provider')
  }
  return ctx
}

export function useWishlyUser(): WishlyUser {
  return useContext(UserContext)
}
