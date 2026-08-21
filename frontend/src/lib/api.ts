/**
 * Authenticated fetch wrapper for the Wishly FastAPI backend (T6.2).
 *
 * Attaches the Clerk session JWT as a Bearer token and targets
 * ``VITE_API_BASE_URL``. All business logic lives server-side; the SPA
 * only talks to the world through these helpers.
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

type TokenGetter = () => Promise<string | null>

/** Perform an authenticated request against the Wishly API. */
export async function apiFetch<T>(
  path: string,
  getToken: TokenGetter,
  init: RequestInit = {}
): Promise<T> {
  if (MOCK_API) {
    return mockFetch<T>(path, init)
  }

  const token = await getToken()
  if (!token) {
    throw new ApiError(401, null, 'Not authenticated')
  }

  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, headers })
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
    throw new ApiError(response.status, body)
  }

  return body as T
}

// --- Response types (mirror backend schemas) -------------------------------- //

export type User = {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  timezone: string
  send_hour: number
  /** ISO timestamp, or null if onboarding has not been completed. */
  onboarded_at: string | null
  created_at: string
  updated_at: string
}

export type UserUpdate = {
  /** Set once by the onboarding flow; the server stamps ``onboarded_at``. */
  onboarded?: boolean
  timezone?: string
  send_hour?: number
}

export type EventType = 'birthday' | 'anniversary' | 'custom'

export type Event = {
  id: string
  user_id: string
  title: string
  event_type: EventType
  event_month: number
  event_day: number
  event_year: number | null
  message: string | null
  recipient_email: string | null
  recipient_name: string | null
  template_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  reminders: number[]
}

export type EventCreate = {
  title: string
  event_type: EventType
  event_month: number
  event_day: number
  event_year?: number | null
  message?: string | null
  is_active?: boolean
}

export type EventUpdate = Partial<EventCreate>

/**
 * Mirrors notification_log.status exactly. The API returns the ledger's own value
 * rather than translating it, so the UI and the table you'd query when debugging
 * never disagree. ('skipped' is what a suppressed recipient records.)
 */
export type NotificationStatus = 'pending' | 'sent' | 'failed' | 'skipped'

/** One row of the send log (notification_log), enriched with event details. */
export type Notification = {
  id: string
  /** Null for test reminders, which belong to no event. */
  event_id: string | null
  event_title: string
  event_type: EventType
  days_before: number
  occurrence_date: string
  status: NotificationStatus
  /** True for a test reminder sent from the Account page. */
  is_test: boolean
  /** Null unless the send actually succeeded. */
  sent_at: string | null
  created_at: string
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
