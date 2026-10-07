/**
 * Auth providers — the component half of the auth layer.
 *
 * Two implementations, chosen once at the top of the tree:
 *  - **Session token** (default): POST /auth/login or /auth/signup returns an
 *    opaque token, kept in localStorage and sent as a Bearer token. Signing out
 *    deletes the session on the server too.
 *  - **Dev bypass** (`VITE_DEV_NO_AUTH=true`): a fixed, always-signed-in user,
 *    for running the UI against the in-browser mock.
 *
 * Components consume `useWishlyAuth()` (from auth-context) and never touch
 * localStorage or the token directly.
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { apiFetch, setUnauthorizedHandler, type Session } from './api.ts'
import { AuthContext, DEV_NO_AUTH, type WishlyAuth } from './auth-context.ts'

const STORAGE_KEY = 'wishly.session'

// localStorage can be missing or throw (private windows, blocked storage).
// Signing in still works then; it just doesn't survive a reload.
function readStoredToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function writeStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(STORAGE_KEY, token)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // Ignore: see readStoredToken.
  }
}

function SessionAuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState<string | null>(readStoredToken)

  /** Switch sessions. Cached data belongs to the previous user, so drop it. */
  const saveToken = useCallback(
    (next: string | null) => {
      writeStoredToken(next)
      setToken(next)
      queryClient.clear()
    },
    [queryClient]
  )

  // An expired or revoked session makes the API answer 401: forget the token,
  // and the protected routes send the user to /sign-in.
  useEffect(() => {
    setUnauthorizedHandler(() => saveToken(null))
    return () => setUnauthorizedHandler(null)
  }, [saveToken])

  const startSession = useCallback(
    async (path: string, email: string, password: string) => {
      const session = await apiFetch<Session>(path, null, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      saveToken(session.token)
    },
    [saveToken]
  )

  const auth = useMemo<WishlyAuth>(
    () => ({
      isLoaded: true,
      isSignedIn: token !== null,
      getToken: async () => token,
      signIn: (email, password) => startSession('/auth/login', email, password),
      signUp: (email, password) => startSession('/auth/signup', email, password),
      signOut: async () => {
        if (token) {
          try {
            await apiFetch<void>('/auth/logout', async () => token, { method: 'POST' })
          } catch {
            // The server may already consider it gone; forget it locally regardless.
          }
        }
        saveToken(null)
      },
    }),
    [token, startSession, saveToken]
  )

  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

/** Fixed, always-signed-in dev user for mock mode. */
function DevAuthProvider({ children }: { children: ReactNode }) {
  const auth = useMemo<WishlyAuth>(
    () => ({
      isLoaded: true,
      isSignedIn: true,
      getToken: async () => 'dev-no-auth',
      signIn: async () => {},
      signUp: async () => {},
      signOut: async () => {},
    }),
    []
  )
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

/** Pick the provider for the current mode. Must render inside QueryClientProvider. */
export function AuthProvider({ children }: { children: ReactNode }) {
  return DEV_NO_AUTH ? (
    <DevAuthProvider>{children}</DevAuthProvider>
  ) : (
    <SessionAuthProvider>{children}</SessionAuthProvider>
  )
}
