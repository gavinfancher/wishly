import { Icon } from './Win98.tsx'
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
  selected: boolean
  onSelect: (reminder: Reminder) => void
  onEdit: (reminder: Reminder) => void
  onDelete: (reminder: Reminder) => void
  onContextMenu: (reminder: Reminder, x: number, y: number) => void
}

/**
 * One reminder in the Explorer-style list. Click selects, double-click or Enter
 * opens its properties, Delete asks to remove it, right-click shows the menu.
 */
export default function ReminderRow({
  reminder,
  selected,
  onSelect,
  onEdit,
  onDelete,
  onContextMenu,
}: ReminderRowProps) {
  const days = daysUntil(reminder.month, reminder.day)
  const nextEmail = daysUntilNextReminder(days, reminder.days_before)

  return (
    <tr
      tabIndex={0}
      aria-selected={selected}
      className={selected ? 'is-selected' : undefined}
      onClick={() => onSelect(reminder)}
      onDoubleClick={() => onEdit(reminder)}
      onContextMenu={(e) => {
        e.preventDefault()
        onSelect(reminder)
        onContextMenu(reminder, e.clientX, e.clientY)
      }}
      onFocus={() => onSelect(reminder)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          onEdit(reminder)
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
          e.preventDefault()
          onDelete(reminder)
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault()
          const sibling =
            e.key === 'ArrowDown'
              ? e.currentTarget.nextElementSibling
              : e.currentTarget.previousElementSibling
          ;(sibling as HTMLElement | null)?.focus()
        }
      }}
    >
      <td>
        <span className="cell-name">
          <Icon name="calendar" />
          <span>{reminder.title}</span>
        </span>
      </td>
      <td>
        {monthAbbr(reminder.month)} {reminder.day}
      </td>
      <td className={days <= 7 ? 'cell-soon' : undefined}>{countdownLabel(days)}</td>
      <td className="col-wide">{reminder.days_before.map(formatReminderLabel).join(', ')}</td>
      <td>{nextEmail !== null ? nextReminderLabel(nextEmail) : '—'}</td>
    </tr>
  )
}
