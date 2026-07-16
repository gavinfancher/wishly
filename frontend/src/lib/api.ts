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

  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, headers })

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
  created_at: string
  updated_at: string
}

export type UserUpdate = {
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

export type NotificationStatus = 'sent' | 'failed' | 'suppressed'

/** One row of the send log (notification_log), enriched with event details. */
export type Notification = {
  id: string
  event_id: string
  event_title: string
  event_type: EventType
  days_before: number
  occurrence_date: string
  status: NotificationStatus
  sent_at: string
}
