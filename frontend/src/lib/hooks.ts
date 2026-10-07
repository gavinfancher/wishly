/**
 * React Query hooks for the Wishly API.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useWishlyAuth } from './auth-context.ts'

import { apiFetch, type Reminder, type ReminderInput, type User, type UserUpdate } from './api.ts'

function useGetToken() {
  const { getToken } = useWishlyAuth()
  return getToken
}

/** Current user profile (created server-side on first request). */
export function useMe() {
  const getToken = useGetToken()

  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<User>('/me', getToken),
  })
}

/** Update timezone / send hour, or finish onboarding. */
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

/** Email the signed-in user a sample reminder, to check delivery works. */
export function useSendTestEmail() {
  const getToken = useGetToken()

  return useMutation({
    mutationFn: () => apiFetch<{ status: string }>('/me/test-email', getToken, { method: 'POST' }),
  })
}

/** The current user's reminders. */
export function useReminders() {
  const getToken = useGetToken()

  return useQuery({
    queryKey: ['reminders'],
    queryFn: () => apiFetch<Reminder[]>('/reminders', getToken),
  })
}

/** Create a reminder, or replace an existing one when `id` is given. */
export function useSaveReminder() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: ReminderInput }) =>
      id !== undefined
        ? apiFetch<Reminder>(`/reminders/${id}`, getToken, {
            method: 'PUT',
            body: JSON.stringify(body),
          })
        : apiFetch<Reminder>('/reminders', getToken, {
            method: 'POST',
            body: JSON.stringify(body),
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reminders'] })
    },
  })
}

export function useDeleteReminder() {
  const getToken = useGetToken()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/reminders/${id}`, getToken, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reminders'] })
    },
  })
}
