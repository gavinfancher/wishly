import type { Event } from '../lib/api.ts'
import { countdownLabel, daysUntil, monthAbbr, yearsAtNext } from '../lib/dates.ts'

type EventRowProps = {
  event: Event
  onEdit: (event: Event) => void
  onDelete: (event: Event) => void
  onToggleActive: (event: Event) => void
  isDeleting: boolean
  isToggling: boolean
}

const TYPE_LABELS: Record<Event['event_type'], string> = {
  birthday: 'Birthday',
  anniversary: 'Anniversary',
  custom: 'Custom',
}

function reminderSummary(reminders: number[]): string | null {
  if (reminders.length === 0) return null
  const sorted = [...reminders].sort((a, b) => b - a)
  const parts = sorted.map((d) => (d === 0 ? 'day of' : `${d}d`))
  return `Reminds ${parts.join(' · ')}`
}

/** One occasion in the agenda list: date leaf, details, countdown, actions. */
export default function EventRow({
  event,
  onEdit,
  onDelete,
  onToggleActive,
  isDeleting,
  isToggling,
}: EventRowProps) {
  const days = daysUntil(event.event_month, event.event_day)
  const years = yearsAtNext(event.event_year, event.event_month, event.event_day)
  const summary = reminderSummary(event.reminders)

  const milestone =
    years === null
      ? null
      : event.event_type === 'birthday'
        ? `turns ${years}`
        : event.event_type === 'anniversary'
          ? `${years} years`
          : `year ${years}`

  const countdownClass = !event.is_active
    ? 'row-count row-count-paused'
    : days <= 7
      ? 'row-count row-count-soon'
      : 'row-count'

  return (
    <li className={`event-row ${event.is_active ? '' : 'event-row-paused'}`}>
      <div className="row-leaf" aria-hidden="true">
        <span className="leaf-month">{monthAbbr(event.event_month)}</span>
        <span className="leaf-day">{event.event_day}</span>
      </div>

      <div className="row-main">
        <h3 className="row-title">{event.title}</h3>
        <p className="row-meta">
          {TYPE_LABELS[event.event_type]}
          {milestone && <> · {milestone}</>}
          {summary && <> · {summary}</>}
        </p>
        {event.message && <p className="row-note">{event.message}</p>}
      </div>

      <div className="row-side">
        <span className={countdownClass}>{event.is_active ? countdownLabel(days) : 'Paused'}</span>
        <div className="row-actions">
          <button type="button" className="btn-quiet" onClick={() => onEdit(event)}>
            Edit
          </button>
          <button
            type="button"
            className="btn-quiet"
            onClick={() => onToggleActive(event)}
            disabled={isToggling}
          >
            {isToggling ? '…' : event.is_active ? 'Pause' : 'Resume'}
          </button>
          <button
            type="button"
            className="btn-quiet btn-quiet-danger"
            onClick={() => onDelete(event)}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </li>
  )
}
