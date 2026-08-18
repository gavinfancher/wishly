import { useEffect, useMemo, useState } from 'react'

import ConfirmDialog from '../components/ConfirmDialog.tsx'
import EventRow from '../components/EventRow.tsx'
import EventForm, { type EventFormValues } from '../components/EventForm.tsx'
import type { Event, EventType } from '../lib/api.ts'
import { daysUntil } from '../lib/dates.ts'
import {
  useCreateEvent,
  useDeleteEvent,
  useEvents,
  useMe,
  useReplaceReminders,
  useUpdateEvent,
} from '../lib/hooks.ts'

type TypeFilter = 'all' | EventType
type SortOrder = 'soonest' | 'title' | 'newest'

const TYPE_FILTERS: { value: TypeFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'birthday', label: 'Birthdays' },
  { value: 'anniversary', label: 'Anniversaries' },
  { value: 'custom', label: 'Custom' },
]

function sortEvents(events: Event[], order: SortOrder): Event[] {
  const sorted = [...events]
  switch (order) {
    case 'title':
      return sorted.sort((a, b) => a.title.localeCompare(b.title))
    case 'newest':
      return sorted.sort((a, b) => b.created_at.localeCompare(a.created_at))
    case 'soonest':
      return sorted.sort(
        (a, b) => daysUntil(a.event_month, a.event_day) - daysUntil(b.event_month, b.event_day)
      )
  }
}

/**
 * The agenda: every occasion sorted by how soon it comes around, with
 * search / filter / sort, create / edit / delete, inline pause, and
 * reminder management (T6.4).
 */
export default function EventsPage() {
  const { data: profile } = useMe()
  const { data: events, isLoading, isError, refetch } = useEvents()
  const createEvent = useCreateEvent()
  const updateEvent = useUpdateEvent()
  const deleteEvent = useDeleteEvent()
  const replaceReminders = useReplaceReminders()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Event | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Event | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [sortOrder, setSortOrder] = useState<SortOrder>('soonest')

  const isSaving = createEvent.isPending || updateEvent.isPending || replaceReminders.isPending
  const hasEvents = (events?.length ?? 0) > 0

  const { upcoming, paused, hiddenByFilters } = useMemo(() => {
    const query = search.trim().toLowerCase()
    const visible = (events ?? []).filter(
      (e) =>
        (typeFilter === 'all' || e.event_type === typeFilter) &&
        (query === '' || e.title.toLowerCase().includes(query))
    )
    return {
      upcoming: sortEvents(
        visible.filter((e) => e.is_active),
        sortOrder
      ),
      paused: sortEvents(
        visible.filter((e) => !e.is_active),
        sortOrder
      ),
      hiddenByFilters: (events?.length ?? 0) - visible.length,
    }
  }, [events, search, typeFilter, sortOrder])

  useEffect(() => {
    if (!modalOpen) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isSaving) {
        setModalOpen(false)
        setEditing(null)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [modalOpen, isSaving])

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

  async function handleDeleteConfirmed() {
    if (!confirmDelete) return
    try {
      await deleteEvent.mutateAsync(confirmDelete.id)
    } finally {
      setConfirmDelete(null)
    }
  }

  async function handleToggleActive(event: Event) {
    setTogglingId(event.id)
    try {
      await updateEvent.mutateAsync({ id: event.id, body: { is_active: !event.is_active } })
    } finally {
      setTogglingId(null)
    }
  }

  const rowProps = (event: Event) => ({
    event,
    onEdit: openEdit,
    onDelete: setConfirmDelete,
    onToggleActive: (e: Event) => void handleToggleActive(e),
    isDeleting: deleteEvent.isPending && confirmDelete?.id === event.id,
    isToggling: togglingId === event.id,
  })

  return (
    <div className="events-page">
      <header className="events-header">
        <div>
          {profile && (
            <p className="events-subtitle">
              Reminders land around{' '}
              <span className="mono">{String(profile.send_hour).padStart(2, '0')}:00</span> ·{' '}
              {profile.timezone}
            </p>
          )}
        </div>
      </header>

      {hasEvents && (
        <div className="toolbar">
          <input
            type="search"
            className="toolbar-search"
            placeholder="Search occasions…"
            aria-label="Search occasions"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="filter-chips" role="group" aria-label="Filter by type">
            {TYPE_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`chip ${typeFilter === filter.value ? 'chip-active' : ''}`}
                aria-pressed={typeFilter === filter.value}
                onClick={() => setTypeFilter(filter.value)}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <select
            className="toolbar-sort"
            aria-label="Sort order"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as SortOrder)}
          >
            <option value="soonest">Soonest first</option>
            <option value="title">A to Z</option>
            <option value="newest">Recently added</option>
          </select>
          <button type="button" className="btn-primary btn-compact" onClick={openCreate}>
            Add a date
          </button>
        </div>
      )}

      {isLoading && <p className="events-status">Loading your dates…</p>}

      {isError && (
        <div className="events-status events-error">
          <p>Could not load your dates.</p>
          <button type="button" className="btn-secondary" onClick={() => void refetch()}>
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && !hasEvents && (
        <div className="events-empty">
          <h2>Nothing circled yet</h2>
          <p>Add a birthday, an anniversary, or any date you can’t afford to forget.</p>
          <button type="button" className="btn-primary" onClick={openCreate}>
            Add your first date
          </button>
        </div>
      )}

      {hasEvents && upcoming.length === 0 && paused.length === 0 && (
        <div className="events-empty">
          <h2>No matches</h2>
          <p>
            {hiddenByFilters} occasion{hiddenByFilters === 1 ? ' is' : 's are'} hidden by your
            search or filters.
          </p>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setSearch('')
              setTypeFilter('all')
            }}
          >
            Clear filters
          </button>
        </div>
      )}

      {upcoming.length > 0 && (
        <ul className="events-list">
          {upcoming.map((event) => (
            <EventRow key={event.id} {...rowProps(event)} />
          ))}
        </ul>
      )}

      {paused.length > 0 && (
        <>
          <h2 className="events-section-label">Paused</h2>
          <ul className="events-list">
            {paused.map((event) => (
              <EventRow key={event.id} {...rowProps(event)} />
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

      {confirmDelete && (
        <ConfirmDialog
          title={`Delete “${confirmDelete.title}”?`}
          body="The occasion and its reminder schedule will be removed. This cannot be undone."
          confirmLabel="Delete occasion"
          danger
          isBusy={deleteEvent.isPending}
          onConfirm={() => void handleDeleteConfirmed()}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  )
}
