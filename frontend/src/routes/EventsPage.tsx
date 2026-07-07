import { useState } from 'react'

import { useWishlyUser } from '../lib/auth-context.ts'
import EventRow from '../components/EventRow.tsx'
import EventForm, { type EventFormValues } from '../components/EventForm.tsx'
import type { Event } from '../lib/api.ts'
import { daysUntil } from '../lib/dates.ts'
import {
  useCreateEvent,
  useDeleteEvent,
  useEvents,
  useMe,
  useReplaceReminders,
  useUpdateEvent,
} from '../lib/hooks.ts'

/**
 * The agenda: every occasion sorted by how soon it comes around, with
 * create / edit / delete and reminder management (T6.4).
 */
export default function EventsPage() {
  const { firstName } = useWishlyUser()
  const { data: profile } = useMe()
  const { data: events, isLoading, isError, refetch } = useEvents()
  const createEvent = useCreateEvent()
  const updateEvent = useUpdateEvent()
  const deleteEvent = useDeleteEvent()
  const replaceReminders = useReplaceReminders()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Event | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const isSaving = createEvent.isPending || updateEvent.isPending || replaceReminders.isPending

  const byNextOccurrence = (a: Event, b: Event) =>
    daysUntil(a.event_month, a.event_day) - daysUntil(b.event_month, b.event_day)
  const upcoming = (events ?? []).filter((e) => e.is_active).sort(byNextOccurrence)
  const paused = (events ?? []).filter((e) => !e.is_active).sort(byNextOccurrence)

  function openCreate() {
    setEditing(null)
    setModalOpen(true)
  }

  function openEdit(event: Event) {
    setEditing(event)
    setModalOpen(true)
  }

  function closeModal() {
    if (isSaving) return
    setModalOpen(false)
    setEditing(null)
  }

  async function handleSave(values: EventFormValues) {
    const body = {
      title: values.title.trim(),
      event_type: values.event_type,
      event_month: values.event_month,
      event_day: values.event_day,
      event_year: values.event_year.trim() ? Number(values.event_year) : null,
      message: values.message.trim() || null,
      is_active: values.is_active,
    }

    let eventId: string

    if (editing) {
      await updateEvent.mutateAsync({ id: editing.id, body })
      eventId = editing.id
    } else {
      const created = await createEvent.mutateAsync(body)
      eventId = created.id
    }

    await replaceReminders.mutateAsync({ id: eventId, days_before: values.reminders })
    closeModal()
  }

  async function handleDelete(event: Event) {
    const confirmed = window.confirm(`Delete "${event.title}"? This cannot be undone.`)
    if (!confirmed) return

    setDeletingId(event.id)
    try {
      await deleteEvent.mutateAsync(event.id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="events-page">
      <header className="events-header">
        <div>
          <h1>Coming up{firstName ? ` for ${firstName}` : ''}</h1>
          {profile && (
            <p className="events-subtitle">
              Reminders land around{' '}
              <span className="mono">{String(profile.send_hour).padStart(2, '0')}:00</span> ·{' '}
              {profile.timezone}
            </p>
          )}
        </div>
        <button type="button" className="btn-primary" onClick={openCreate}>
          Add a date
        </button>
      </header>

      {isLoading && <p className="events-status">Loading your dates…</p>}

      {isError && (
        <div className="events-status events-error">
          <p>Could not load your dates.</p>
          <button type="button" className="btn-secondary" onClick={() => void refetch()}>
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && events?.length === 0 && (
        <div className="events-empty">
          <h2>Nothing circled yet</h2>
          <p>Add a birthday, an anniversary, or any date you can’t afford to forget.</p>
          <button type="button" className="btn-primary" onClick={openCreate}>
            Add your first date
          </button>
        </div>
      )}

      {upcoming.length > 0 && (
        <ul className="events-list">
          {upcoming.map((event) => (
            <EventRow
              key={event.id}
              event={event}
              onEdit={openEdit}
              onDelete={handleDelete}
              isDeleting={deletingId === event.id}
            />
          ))}
        </ul>
      )}

      {paused.length > 0 && (
        <>
          <h2 className="events-section-label">Paused</h2>
          <ul className="events-list">
            {paused.map((event) => (
              <EventRow
                key={event.id}
                event={event}
                onEdit={openEdit}
                onDelete={handleDelete}
                isDeleting={deletingId === event.id}
              />
            ))}
          </ul>
        </>
      )}

      {modalOpen && (
        <div className="modal-overlay" role="presentation" onClick={closeModal}>
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="event-form-title"
            onClick={(e) => e.stopPropagation()}
          >
            <EventForm
              initial={editing}
              onSubmit={handleSave}
              onCancel={closeModal}
              isSubmitting={isSaving}
            />
          </div>
        </div>
      )}
    </div>
  )
}
