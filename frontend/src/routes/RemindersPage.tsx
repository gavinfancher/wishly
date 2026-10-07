import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import AccountInfoDialog from '../components/AccountInfoDialog.tsx'
import ConfirmDialog from '../components/ConfirmDialog.tsx'
import ContextMenu from '../components/ContextMenu.tsx'
import MenuBar from '../components/MenuBar.tsx'
import ReminderForm from '../components/ReminderForm.tsx'
import ReminderRow from '../components/ReminderRow.tsx'
import TestEmailDialog from '../components/TestEmailDialog.tsx'
import TimeZoneDialog from '../components/TimeZoneDialog.tsx'
import { Icon, Message, Window } from '../components/Win98.tsx'
import type { Reminder, ReminderInput } from '../lib/api.ts'
import { DEV_NO_AUTH, useWishlyAuth } from '../lib/auth-context.ts'
import { daysUntil } from '../lib/dates.ts'
import { useDeleteReminder, useMe, useReminders, useSaveReminder } from '../lib/hooks.ts'
import { useEscape } from '../lib/useEscape.ts'

/**
 * The Wishly window's contents: menu bar, toolbar, every reminder soonest
 * first, status bar. `/app/account` is this same view with File › Account Info
 * open over it, so the URL still links straight to it.
 */
export default function RemindersPage() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { signOut } = useWishlyAuth()
  const accountOpen = pathname === '/app/account'
  const [aboutOpen, setAboutOpen] = useState(false)
  const [timeZoneOpen, setTimeZoneOpen] = useState(false)
  const [testEmailOpen, setTestEmailOpen] = useState(false)
  const closeAbout = useCallback(() => setAboutOpen(false), [])
  const closeAccount = useCallback(() => navigate('/app'), [navigate])
  const closeTimeZone = useCallback(() => setTimeZoneOpen(false), [])
  const closeTestEmail = useCallback(() => setTestEmailOpen(false), [])
  useEscape(closeAbout, !aboutOpen)

  const { data: profile } = useMe()
  const { data: reminders, isLoading, isError, refetch } = useReminders()
  const saveReminder = useSaveReminder()
  const deleteReminder = useDeleteReminder()

  // undefined = form closed, null = adding a new one, Reminder = editing that one.
  const [editing, setEditing] = useState<Reminder | null | undefined>(undefined)
  const [confirmDelete, setConfirmDelete] = useState<Reminder | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [menu, setMenu] = useState<{ reminder: Reminder; x: number; y: number } | null>(null)
  const closeMenu = useCallback(() => setMenu(null), [])

  const sorted = [...(reminders ?? [])].sort(
    (a, b) => daysUntil(a.month, a.day) - daysUntil(b.month, b.day)
  )
  const selected = sorted.find((r) => r.id === selectedId) ?? null

  useEffect(() => {
    if (editing === undefined) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !saveReminder.isPending) setEditing(undefined)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [editing, saveReminder.isPending])

  async function handleSave(body: ReminderInput) {
    const saved = await saveReminder.mutateAsync({ id: editing?.id, body })
    setSelectedId(saved.id)
    setEditing(undefined)
  }

  async function handleDeleteConfirmed() {
    if (!confirmDelete) return
    try {
      await deleteReminder.mutateAsync(confirmDelete.id)
      setSelectedId(null)
    } finally {
      setConfirmDelete(null)
    }
  }

  let status = `${sorted.length} reminder(s)`
  if (isLoading) status = 'Loading...'

  return (
    <div className="page">
      <MenuBar
        menus={[
          {
            label: 'File',
            items: [
              { label: 'Account Info...', onSelect: () => navigate('/app/account') },
              { label: 'Time Zone...', onSelect: () => setTimeZoneOpen(true) },
              { label: 'Send Test E-mail...', onSelect: () => setTestEmailOpen(true) },
              { separator: true },
              // Once the token is gone, the layout redirects to /sign-in by itself.
              { label: 'Log Off...', disabled: DEV_NO_AUTH, onSelect: () => void signOut() },
            ],
          },
          {
            label: 'Help',
            items: [{ label: 'About Wishly', onSelect: () => setAboutOpen(true) }],
          },
        ]}
      />

      <div className="toolbar" role="toolbar" aria-label="Reminders">
        <button type="button" className="tool" onClick={() => setEditing(null)}>
          <Icon name="new" size={20} />
          New
        </button>
        <button
          type="button"
          className="tool"
          disabled={!selected}
          onClick={() => selected && setEditing(selected)}
        >
          <Icon name="props" size={20} />
          Properties
        </button>
        <span className="tool-sep" aria-hidden="true" />
        <button
          type="button"
          className="tool"
          disabled={!selected}
          onClick={() => selected && setConfirmDelete(selected)}
        >
          <Icon name="delete" size={20} />
          Delete
        </button>
      </div>

      <section className="pane list-pane" aria-label="Reminders">
        {isError ? (
          <div className="empty">
            <p>Could not load your reminders.</p>
            <button type="button" className="btn" onClick={() => void refetch()}>
              Retry
            </button>
          </div>
        ) : (
          <div className="scroll">
            <table className="list">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Date</th>
                  <th>Occurs</th>
                  <th className="col-wide">E-mail Me</th>
                  <th>Next E-mail</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((reminder) => (
                  <ReminderRow
                    key={reminder.id}
                    reminder={reminder}
                    selected={reminder.id === selectedId}
                    onSelect={(r) => setSelectedId(r.id)}
                    onEdit={setEditing}
                    onDelete={setConfirmDelete}
                    onContextMenu={(r, x, y) => setMenu({ reminder: r, x, y })}
                  />
                ))}
              </tbody>
            </table>

            {!isLoading && sorted.length === 0 && (
              <div className="empty">
                <p>
                  <b>Nothing circled yet.</b>
                </p>
                <p>Pick a date, pick how many days ahead you want an e-mail. That’s it.</p>
                <button type="button" className="btn btn-default" onClick={() => setEditing(null)}>
                  New Reminder...
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      <div className="statusbar">
        <div className="statusbar-main">{status}</div>
        {profile && (
          <div>
            E-mails at {String(profile.send_hour).padStart(2, '0')}:00 · {profile.timezone}
          </div>
        )}
      </div>

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={closeMenu}
          items={[
            { label: 'Properties', bold: true, onSelect: () => setEditing(menu.reminder) },
            { label: 'Delete', onSelect: () => setConfirmDelete(menu.reminder) },
          ]}
        />
      )}

      {editing !== undefined && (
        <div className="veil" role="presentation">
          <ReminderForm
            initial={editing}
            onSubmit={handleSave}
            onCancel={() => setEditing(undefined)}
            isSubmitting={saveReminder.isPending}
          />
        </div>
      )}

      {accountOpen && <AccountInfoDialog onClose={closeAccount} />}
      {timeZoneOpen && <TimeZoneDialog onClose={closeTimeZone} />}
      {testEmailOpen && <TestEmailDialog onClose={closeTestEmail} />}

      {aboutOpen && (
        <div className="veil" role="presentation" onClick={closeAbout}>
          <Window
            title="About Wishly"
            dialog="alertdialog"
            className="dialog"
            onClose={() => setAboutOpen(false)}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="body">
              <Message icon="info">
                <p>
                  <b>Wishly</b>
                </p>
                <p>
                  Reminders for the dates that matter. Pick a date, pick how many days ahead you
                  want an e-mail, and Wishly sends it every year.
                </p>
              </Message>
              <div className="row center">
                <button
                  type="button"
                  className="btn btn-default"
                  onClick={() => setAboutOpen(false)}
                  autoFocus
                >
                  OK
                </button>
              </div>
            </div>
          </Window>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Confirm Reminder Delete"
          body={`Are you sure you want to delete ‘${confirmDelete.title}’? You won’t get any more e-mails for it.`}
          danger
          isBusy={deleteReminder.isPending}
          onConfirm={() => void handleDeleteConfirmed()}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  )
}
