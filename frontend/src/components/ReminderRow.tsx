import RowMenu from './RowMenu.tsx'
import type { Reminder } from '../lib/api.ts'
import {
  countdownLabel,
  daysUntil,
  daysUntilNextReminder,
  monthAbbr,
  nextReminderLabel,
} from '../lib/dates.ts'
import { formatReminderLabel } from '../lib/validation.ts'

type ReminderRowProps = {
  reminder: Reminder
  onEdit: (reminder: Reminder) => void
  onDelete: (reminder: Reminder) => void
}

/**
 * One reminder in the list: date leaf, title, cadence, countdown, actions menu.
 * The title button is stretched over the whole row in CSS, so clicking anywhere
 * opens the editor.
 */
export default function ReminderRow({ reminder, onEdit, onDelete }: ReminderRowProps) {
  const days = daysUntil(reminder.month, reminder.day)
  const nextEmail = daysUntilNextReminder(days, reminder.days_before)

  return (
    <li className="event-row">
      <div className="row-leaf" aria-hidden="true">
        <span className="leaf-month">{monthAbbr(reminder.month)}</span>
        <span className="leaf-day">{reminder.day}</span>
      </div>

      <div className="row-main">
        <h3 className="row-title">
          <button type="button" className="row-open" onClick={() => onEdit(reminder)}>
            {reminder.title}
          </button>
        </h3>
        <p className="row-meta">
          {reminder.days_before.map(formatReminderLabel).join(', ')}
          {nextEmail !== null && <> · Next email {nextReminderLabel(nextEmail)}</>}
        </p>
      </div>

      <div className="row-side">
        <span className={days <= 7 ? 'row-count row-count-soon' : 'row-count'}>
          {countdownLabel(days)}
        </span>
        <RowMenu
          label={reminder.title}
          items={[
            { label: 'Edit', onSelect: () => onEdit(reminder) },
            { label: 'Delete', onSelect: () => onDelete(reminder), danger: true },
          ]}
        />
      </div>
    </li>
  )
}
