import { useEffect, useState } from 'react'

import ConfirmDialog from '../components/ConfirmDialog.tsx'
import ReminderForm from '../components/ReminderForm.tsx'
import ReminderRow from '../components/ReminderRow.tsx'
import type { Reminder, ReminderInput } from '../lib/api.ts'
import { daysUntil } from '../lib/dates.ts'
import { useDeleteReminder, useMe, useReminders, useSaveReminder } from '../lib/hooks.ts'

/** The main page: every reminder, soonest first, with add / edit / delete. */
export default function RemindersPage() {
  const { data: profile } = useMe()
  const { data: reminders, isLoading, isError, refetch } = useReminders()
  const saveReminder = useSaveReminder()
  const deleteReminder = useDeleteReminder()

  // undefined = form closed, null = adding a new one, Reminder = editing that one.
  const [editing, setEditing] = useState<Reminder | null | undefined>(undefined)
  const [confirmDelete, setConfirmDelete] = useState<Reminder | null>(null)

  const sorted = [...(reminders ?? [])].sort(
    (a, b) => daysUntil(a.month, a.day) - daysUntil(b.month, b.day)
  )

  useEffect(() => {
    if (editing === undefined) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !saveReminder.isPending) setEditing(undefined)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [editing, saveReminder.isPending])

  async function handleSave(body: ReminderInput) {
    await saveReminder.mutateAsync({ id: editing?.id, body })
    setEditing(undefined)
  }

  async function handleDeleteConfirmed() {
    if (!confirmDelete) return
    try {
      await deleteReminder.mutateAsync(confirmDelete.id)
    } finally {
      setConfirmDelete(null)
    }
  }

  return (
    <div className="events-page">
      <header className="events-header">
        {profile && (
          <p className="events-subtitle">
            Emails arrive around{' '}
            <span className="mono">{String(profile.send_hour).padStart(2, '0')}:00</span> ·{' '}
            {profile.timezone}
          </p>
        )}
        {sorted.length > 0 && (
          <button
            type="button"
            className="btn-primary btn-compact"
            onClick={() => setEditing(null)}
          >
            Add a reminder
          </button>
        )}
      </header>

      {isLoading && <p className="events-status">Loading your reminders…</p>}

      {isError && (
        <div className="events-status events-error">
          <p>Could not load your reminders.</p>
          <button type="button" className="btn-secondary" onClick={() => void refetch()}>
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && sorted.length === 0 && (
        <div className="events-empty">
          <h2>Nothing circled yet</h2>
          <p>Pick a date, pick how many days ahead you want an email. That’s it.</p>
          <button type="button" className="btn-primary" onClick={() => setEditing(null)}>
            Add your first reminder
          </button>
        </div>
      )}

      {sorted.length > 0 && (
        <ul className="events-list">
          {sorted.map((reminder) => (
            <ReminderRow
              key={reminder.id}
              reminder={reminder}
              onEdit={setEditing}
              onDelete={setConfirmDelete}
            />
          ))}
        </ul>
      )}

      {editing !== undefined && (
        <div className="modal-overlay" role="presentation">
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reminder-form-title"
          >
            <ReminderForm
              initial={editing}
              onSubmit={handleSave}
              onCancel={() => setEditing(undefined)}
              isSubmitting={saveReminder.isPending}
            />
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title={`Delete “${confirmDelete.title}”?`}
          body="You won’t get any more emails for it. This cannot be undone."
          confirmLabel="Delete reminder"
          danger
          isBusy={deleteReminder.isPending}
          onConfirm={() => void handleDeleteConfirmed()}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  )
}
