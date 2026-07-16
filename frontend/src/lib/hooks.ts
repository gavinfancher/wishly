/**
 * React Query hooks for the Wishly API (T6.2).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useWishlyAuth } from './auth-context.ts'

import {
  apiFetch,
  type Event,
  type EventCreate,
  type EventUpdate,
  type Notification,
  type User,
  type UserUpdate,
} from './api.ts'

function useGetToken() {
  const { getToken } = useWishlyAuth()
  return getToken
}

/** Current user profile (provisions on first request server-side). */
export function useMe() {
  const getToken = useGetToken()

  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<User>('/me', getToken),
  })
}

/** Update onboarding preferences (timezone, send_hour). */
export function useUpdateMe() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: UserUpdate) =>
      apiFetch<User>('/me', getToken, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: (user) => {
      queryClient.setQueryData(['me'], user)
    },
  })
}

/** Send a test reminder email to the account owner's inbox. */
export function useSendTestEmail() {
  const getToken = useGetToken()

  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>('/me/test-email', getToken, { method: 'POST' }),
  })
}

/** The send log: reminders Wishly has already emailed, newest first. */
export function useNotifications() {
  const getToken = useGetToken()

  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiFetch<Notification[]>('/notifications', getToken),
  })
}

/** List the current user's events. */
export function useEvents() {
  const getToken = useGetToken()

  return useQuery({
    queryKey: ['events'],
    queryFn: () => apiFetch<Event[]>('/events', getToken),
  })
}

/** Create a new event. */
export function useCreateEvent() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: EventCreate) =>
      apiFetch<Event>('/events', getToken, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}

/** Partially update an event. */
export function useUpdateEvent() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: EventUpdate }) =>
      apiFetch<Event>(`/events/${id}`, getToken, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}

/** Delete an event. */
export function useDeleteEvent() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/events/${id}`, getToken, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}

/** Replace the reminder lead times for an event. */
export function useReplaceReminders() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, days_before }: { id: string; days_before: number[] }) =>
      apiFetch<{ event_id: string; days_before: number[] }>(`/events/${id}/reminders`, getToken, {
        method: 'PUT',
        body: JSON.stringify({ days_before }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}
