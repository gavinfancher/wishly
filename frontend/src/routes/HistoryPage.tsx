import { useMemo } from 'react'

import type { Notification, NotificationStatus } from '../lib/api.ts'
import { useNotifications } from '../lib/hooks.ts'

const STATUS_LABELS: Record<NotificationStatus, string> = {
  sent: 'Sent',
  failed: 'Failed',
  suppressed: 'Suppressed',
}

function leadLabel(daysBefore: number): string {
  if (daysBefore === 0) return 'Day-of reminder'
  if (daysBefore === 1) return '1 day ahead'
  return `${daysBefore} days ahead`
}

function sentAtLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function occurrenceLabel(isoDate: string): string {
  // Date-only strings parse as UTC midnight; add T00:00 to pin to local time.
  return new Date(`${isoDate}T00:00`).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
  })
}

/** Month bucket ("June 2026") a notification belongs to, for group headers. */
function monthKey(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

function groupByMonth(notifications: Notification[]): [string, Notification[]][] {
  const groups = new Map<string, Notification[]>()
  for (const n of notifications) {
    const key = monthKey(n.sent_at)
    const bucket = groups.get(key)
    if (bucket) bucket.push(n)
    else groups.set(key, [n])
  }
  return [...groups.entries()]
}

/**
 * The send log: every reminder email Wishly has delivered (or tried to),
 * newest first, grouped by month.
 */
export default function HistoryPage() {
  const { data: notifications, isLoading, isError, refetch } = useNotifications()

  const groups = useMemo(() => groupByMonth(notifications ?? []), [notifications])

  return (
    <div className="history-page">
      <header className="events-header">
        <div>
          <p className="events-subtitle">Every email Wishly has sent on your behalf.</p>
        </div>
      </header>

      {isLoading && <p className="events-status">Loading your history…</p>}

      {isError && (
        <div className="events-status events-error">
          <p>Could not load your history.</p>
          <button type="button" className="btn-secondary" onClick={() => void refetch()}>
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && groups.length === 0 && (
        <div className="events-empty">
          <h2>Nothing sent yet</h2>
          <p>Once a reminder goes out, it shows up here with when and why it was sent.</p>
        </div>
      )}

      {groups.map(([month, items]) => (
        <section key={month}>
          <h2 className="events-section-label">{month}</h2>
          <ul className="history-list">
            {items.map((n) => (
              <li key={n.id} className="history-row">
                <div className="history-main">
                  <h3 className="row-title">{n.event_title}</h3>
                  <p className="row-meta">
                    {leadLabel(n.days_before)} · for {occurrenceLabel(n.occurrence_date)}
                  </p>
                </div>
                <div className="history-side">
                  <span className={`history-status history-status-${n.status}`}>
                    {STATUS_LABELS[n.status]}
                  </span>
                  <span className="history-when mono">{sentAtLabel(n.sent_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
