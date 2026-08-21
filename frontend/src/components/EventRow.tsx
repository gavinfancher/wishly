import RowMenu from './RowMenu.tsx'
import type { Event } from '../lib/api.ts'
import {
  countdownLabel,
  daysUntil,
  daysUntilNextReminder,
  monthAbbr,
  nextReminderLabel,
  yearsAtNext,
} from '../lib/dates.ts'

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

/**
 * One occasion in the agenda list: date leaf, details, countdown, actions menu.
 *
 * The title carries the row's primary action (edit). Its button is stretched over
 * the whole row in CSS, so clicking anywhere opens the editor while the accessible
 * name stays just the occasion title — rather than making the <li> itself a
 * role="button" with interactive children inside it.
 */
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
  const nextReminder = daysUntilNextReminder(days, event.reminders)

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
        <h3 className="row-title">
          <button type="button" className="row-open" onClick={() => onEdit(event)}>
            {event.title}
          </button>
        </h3>
        <p className="row-meta">
          {TYPE_LABELS[event.event_type]}
          {milestone && <> · {milestone}</>}
          {event.is_active && nextReminder !== null && (
            <> · Next reminder {nextReminderLabel(nextReminder)}</>
          )}
        </p>
        {event.message && <p className="row-note">{event.message}</p>}
      </div>

      <div className="row-side">
        <span className={countdownClass}>{event.is_active ? countdownLabel(days) : 'Paused'}</span>
        <RowMenu
          label={event.title}
          items={[
            { label: 'Edit', onSelect: () => onEdit(event) },
            {
              label: isToggling ? '…' : event.is_active ? 'Pause' : 'Resume',
              onSelect: () => onToggleActive(event),
              disabled: isToggling,
            },
            {
              label: isDeleting ? 'Deleting…' : 'Delete',
              onSelect: () => onDelete(event),
              danger: true,
              disabled: isDeleting,
            },
          ]}
        />
      </div>
    </li>
  )
}
