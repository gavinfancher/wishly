/**
 * In-browser mock of the Wishly API, enabled with ``VITE_MOCK_API=true``.
 *
 * Lets the UI run fully populated with `npm run dev` alone — no FastAPI,
 * no Postgres, no Clerk. `apiFetch` dispatches here instead of `fetch`.
 * State lives in memory and resets on reload.
 */

import type { Event, EventCreate, EventUpdate, Notification, User, UserUpdate } from './api.ts'
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
  first_name: 'Gavin',
  last_name: null,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  send_hour: 8,
  created_at: now(),
  updated_at: now(),
}

function seedEvent(
  seed: {
    title: string
    event_type: Event['event_type']
    offsetDays: number
    event_year?: number
    message?: string
    reminders: number[]
    is_active?: boolean
  },
  index: number
): Event {
  const { month, day } = inDays(seed.offsetDays)
  return {
    id: `evt_mock_${index}`,
    user_id: user.id,
    title: seed.title,
    event_type: seed.event_type,
    event_month: month,
    event_day: day,
    event_year: seed.event_year ?? null,
    message: seed.message ?? null,
    recipient_email: null,
    recipient_name: null,
    template_id: null,
    is_active: seed.is_active ?? true,
    created_at: now(),
    updated_at: now(),
    reminders: seed.reminders,
  }
}

let events: Event[] = [
  {
    title: "Grandma's birthday",
    event_type: 'birthday' as const,
    offsetDays: 2,
    event_year: 1941,
    reminders: [7, 1, 0],
    message: 'Call in the morning — she picks up before 10.',
  },
  {
    title: "Mom's birthday",
    event_type: 'birthday' as const,
    offsetDays: 6,
    event_year: 1962,
    reminders: [30, 7, 1, 0],
    message: 'She mentioned the blue ceramic vase at Harlow & Co.',
  },
  {
    title: "Mia & Tom's anniversary",
    event_type: 'anniversary' as const,
    offsetDays: 19,
    event_year: 2018,
    reminders: [14, 1],
  },
  {
    title: "Dad's birthday",
    event_type: 'birthday' as const,
    offsetDays: 45,
    event_year: 1958,
    reminders: [30, 7, 0],
  },
  {
    title: 'Passport renewal deadline',
    event_type: 'custom' as const,
    offsetDays: 88,
    reminders: [60, 30, 7],
    message: 'Photos + form DS-82. Takes 6–8 weeks.',
  },
  {
    title: "Jordan's birthday",
    event_type: 'birthday' as const,
    offsetDays: 112,
    event_year: 1996,
    reminders: [7, 0],
    is_active: false,
  },
].map(seedEvent)

let nextId = events.length + 1

/** ISO date `days` days ago (date-only for occurrences, full ISO for sent_at). */
function daysAgo(days: number, hour = 8): Date {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(hour, 2, 0, 0)
  return d
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function seedNotification(
  seed: {
    eventIndex: number
    days_before: number
    sentDaysAgo: number
    status?: Notification['status']
  },
  index: number
): Notification {
  const event = events[seed.eventIndex]
  const sentAt = daysAgo(seed.sentDaysAgo)
  const occurrence = daysAgo(seed.sentDaysAgo - seed.days_before)
  return {
    id: `ntf_mock_${index}`,
    event_id: event.id,
    event_title: event.title,
    event_type: event.event_type,
    days_before: seed.days_before,
    occurrence_date: isoDate(occurrence),
    status: seed.status ?? 'sent',
    sent_at: sentAt.toISOString(),
  }
}

const notifications: Notification[] = [
  { eventIndex: 0, days_before: 7, sentDaysAgo: 5 },
  { eventIndex: 1, days_before: 30, sentDaysAgo: 24 },
  { eventIndex: 2, days_before: 14, sentDaysAgo: 47 },
  { eventIndex: 3, days_before: 30, sentDaysAgo: 61 },
  { eventIndex: 3, days_before: 7, sentDaysAgo: 84, status: 'failed' as const },
  { eventIndex: 4, days_before: 60, sentDaysAgo: 92 },
  { eventIndex: 5, days_before: 7, sentDaysAgo: 130 },
].map(seedNotification)

const delay = () => new Promise((resolve) => setTimeout(resolve, 180))

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function findEvent(id: string): Event {
  const event = events.find((e) => e.id === id)
  if (!event) throw new ApiError(404, { detail: 'Event not found' })
  return event
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
    const patch = body as UserUpdate
    user = { ...user, ...patch, updated_at: now() }
    return respond(user)
  }

  if (path === '/me/test-email' && method === 'POST') {
    return respond({ status: 'queued' })
  }

  if (path === '/notifications' && method === 'GET') {
    const sorted = [...notifications].sort((a, b) => b.sent_at.localeCompare(a.sent_at))
    return respond(sorted)
  }

  if (path === '/events' && method === 'GET') {
    return respond(events)
  }

  if (path === '/events' && method === 'POST') {
    const create = body as EventCreate
    const event: Event = {
      id: `evt_mock_${nextId++}`,
      user_id: user.id,
      title: create.title,
      event_type: create.event_type,
      event_month: create.event_month,
      event_day: create.event_day,
      event_year: create.event_year ?? null,
      message: create.message ?? null,
      recipient_email: null,
      recipient_name: null,
      template_id: null,
      is_active: create.is_active ?? true,
      created_at: now(),
      updated_at: now(),
      reminders: [],
    }
    events = [...events, event]
    return respond(event)
  }

  const eventMatch = /^\/events\/([^/]+)$/.exec(path)
  if (eventMatch) {
    const event = findEvent(eventMatch[1])

    if (method === 'PATCH') {
      const patch = body as EventUpdate
      const updated = { ...event, ...patch, updated_at: now() }
      events = events.map((e) => (e.id === event.id ? updated : e))
      return respond(updated)
    }

    if (method === 'DELETE') {
      events = events.filter((e) => e.id !== event.id)
      return undefined as T
    }
  }

  const remindersMatch = /^\/events\/([^/]+)\/reminders$/.exec(path)
  if (remindersMatch && method === 'PUT') {
    const event = findEvent(remindersMatch[1])
    const { days_before } = body as { days_before: number[] }
    events = events.map((e) => (e.id === event.id ? { ...e, reminders: days_before } : e))
    return respond({ event_id: event.id, days_before })
  }

  throw new ApiError(404, { detail: `No mock for ${method} ${path}` })
}
