/**
 * In-browser mock of the Wishly API, enabled with ``VITE_MOCK_API=true``.
 *
 * Lets the UI run fully populated with `npm run dev` alone — no FastAPI,
 * no Postgres, no Clerk. `apiFetch` dispatches here instead of `fetch`.
 * State lives in memory and resets on reload.
 */

import type { Reminder, ReminderInput, User, UserUpdate } from './api.ts'
import { ApiError } from './api.ts'

export const MOCK_API = import.meta.env.VITE_MOCK_API === 'true'

const now = () => new Date().toISOString()

/** Month/day of `days` days from today, so seeded countdowns always look alive. */
function inDays(days: number): { month: number; day: number } {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return { month: d.getMonth() + 1, day: d.getDate() }
}

let user: User = {
  id: 'user_mock',
  email: 'you@example.com',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  send_hour: 8,
  onboarded_at: now(),
  created_at: now(),
}

let reminders: Reminder[] = [
  { title: "Grandma's birthday", offsetDays: 2, days_before: [7, 1, 0] },
  { title: "Mom's birthday", offsetDays: 6, days_before: [30, 7, 1, 0] },
  { title: "Mia & Tom's anniversary", offsetDays: 19, days_before: [14, 1] },
  { title: 'Passport renewal deadline', offsetDays: 88, days_before: [60, 30, 7] },
].map((seed, index) => ({
  id: `rem_mock_${index}`,
  title: seed.title,
  ...inDays(seed.offsetDays),
  days_before: seed.days_before,
  created_at: now(),
}))

let nextId = reminders.length

const delay = () => new Promise((resolve) => setTimeout(resolve, 180))

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/** Mirror the server: dedupe, furthest-out first. */
function normalize(body: ReminderInput): ReminderInput {
  return { ...body, days_before: [...new Set(body.days_before)].sort((a, b) => b - a) }
}

/** Handle a request the way the FastAPI backend would. */
export async function mockFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  await delay()

  const method = (init.method ?? 'GET').toUpperCase()
  const body = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
  const respond = (value: unknown) => clone(value) as T

  if (path === '/me' && method === 'GET') {
    return respond(user)
  }

  if (path === '/me' && method === 'PATCH') {
    const { onboarded, ...patch } = body as UserUpdate
    user = {
      ...user,
      ...patch,
      onboarded_at: onboarded ? (user.onboarded_at ?? now()) : user.onboarded_at,
    }
    return respond(user)
  }

  if (path === '/reminders' && method === 'GET') {
    return respond(reminders)
  }

  if (path === '/reminders' && method === 'POST') {
    const reminder: Reminder = {
      id: `rem_mock_${nextId++}`,
      ...normalize(body as ReminderInput),
      created_at: now(),
    }
    reminders = [...reminders, reminder]
    return respond(reminder)
  }

  const match = /^\/reminders\/([^/]+)$/.exec(path)
  if (match) {
    const existing = reminders.find((r) => r.id === match[1])
    if (!existing) throw new ApiError(404, { detail: 'reminder not found' })

    if (method === 'PUT') {
      const updated = { ...existing, ...normalize(body as ReminderInput) }
      reminders = reminders.map((r) => (r.id === existing.id ? updated : r))
      return respond(updated)
    }

    if (method === 'DELETE') {
      reminders = reminders.filter((r) => r.id !== existing.id)
      return undefined as T
    }
  }

  throw new ApiError(404, { detail: `No mock for ${method} ${path}` })
}
