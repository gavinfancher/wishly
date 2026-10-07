/**
 * Fetch wrapper for the Wishly FastAPI backend.
 *
 * Sends the session token (from POST /auth/login or /auth/signup) as a Bearer
 * token and targets ``VITE_API_BASE_URL`` (which includes the ``/v1`` prefix).
 * All business logic lives server-side; the SPA only talks to the world
 * through these helpers.
 */

import { getApiBaseUrl } from './env.ts'
import { MOCK_API, mockFetch } from './mock.ts'

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API error ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

/** How long to wait before calling the API unreachable. See apiFetch. */
export const REQUEST_TIMEOUT_MS = 5_000

type TokenGetter = () => Promise<string | null>

/**
 * Called when the API rejects our token (expired or revoked session). The auth
 * provider registers one that forgets the token, which sends the user back to
 * /sign-in.
 */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

/**
 * Perform a request against the Wishly API. Pass `null` for `getToken` on the
 * calls that happen before there is a session (sign-in, sign-up).
 */
export async function apiFetch<T>(
  path: string,
  getToken: TokenGetter | null,
  init: RequestInit = {}
): Promise<T> {
  if (MOCK_API) {
    return mockFetch<T>(path, init)
  }

  const headers = new Headers(init.headers)
  if (getToken) {
    const token = await getToken()
    if (!token) {
      throw new ApiError(401, null, 'Not authenticated')
    }
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    // Five seconds, then give up and treat it as unreachable. Without this the
    // browser's own timeout applies — often a minute or more — so a failover
    // would leave the user staring at a spinner for far longer than the
    // failover itself takes. A healthy API answers these calls in tens of
    // milliseconds, so 5s only ever fires when something is genuinely wrong.
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers,
      signal: init.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
  } catch {
    // fetch() rejects (rather than resolving with a status) when the request never
    // reached a server at all: the tunnel is down, the host is offline, DNS fails.
    // That is a different situation from an API that answered with an error, and
    // the UI says so instead of blaming the user's profile — see isOffline below.
    throw new ApiError(0, null, 'Wishly is unreachable')
  }

  if (response.status === 204) {
    return undefined as T
  }

  const body: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 401 && getToken) {
      onUnauthorized?.()
    }
    throw new ApiError(response.status, body)
  }

  return body as T
}

// --- Response types (mirror backend/src/wishly/api.py) ---------------------- //

export type User = {
  id: number
  email: string
  timezone: string
  send_hour: number
  /** ISO timestamp, or null if onboarding has not been completed. */
  onboarded_at: string | null
  created_at: string
}

export type UserUpdate = {
  /** Set once by the onboarding flow; the server stamps ``onboarded_at``. */
  onboarded?: boolean
  timezone?: string
  send_hour?: number
}

/** What the form sends: a yearly date, and how many days before it to email. */
export type ReminderInput = {
  title: string
  month: number
  day: number
  /** e.g. [7, 1, 0]. The server dedupes and sorts furthest-first. */
  days_before: number[]
}

export type Reminder = ReminderInput & {
  id: number
  created_at: string
}

/** What POST /auth/login and /auth/signup return. */
export type Session = {
  token: string
  user: User
}

/** The API's own error message (FastAPI's `detail`), if it sent a readable one. */
export function errorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null
  const body = error.body
  if (typeof body !== 'object' || body === null) return null
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined
    if (first && typeof first.msg === 'string') return first.msg
  }
  return null
}

/**
 * Whether a thrown error means the API could not be reached at all.
 *
 * Status 0 is reserved for that case (see the fetch catch above); every real HTTP
 * response carries its own status, so this never confuses a 4xx/5xx with an outage.
 */
export function isOffline(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0
}
