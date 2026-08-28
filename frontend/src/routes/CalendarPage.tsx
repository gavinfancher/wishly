import { useMemo } from 'react'
import { Link } from 'react-router-dom'

import type { Event } from '../lib/api.ts'
import { buildMonthRail, type CalendarMonth } from '../lib/calendar.ts'
import { countdownLabel } from '../lib/dates.ts'
import { useEvents } from '../lib/hooks.ts'

const WEEKDAYS = [
  { short: 'S', full: 'Sunday' },
  { short: 'M', full: 'Monday' },
  { short: 'T', full: 'Tuesday' },
  { short: 'W', full: 'Wednesday' },
  { short: 'T', full: 'Thursday' },
  { short: 'F', full: 'Friday' },
  { short: 'S', full: 'Saturday' },
] as const

const TYPE_LABELS: Record<Event['event_type'], string> = {
  birthday: 'Birthday',
  anniversary: 'Anniversary',
  custom: 'Custom',
}

/** What the countdown column says for one occasion. */
function whenLabel(daysFromToday: number, isActive: boolean): string {
  if (!isActive) return 'Paused'
  if (daysFromToday < 0) return 'Passed'
  return countdownLabel(daysFromToday)
}

function MonthGrid({ month, today }: { month: CalendarMonth; today: Date }) {
  const marked = new Map(month.occasions.map((o) => [o.day, o]))
  const isCurrentMonth =
    today.getFullYear() === month.year && today.getMonth() + 1 === month.month

  return (
    <table className="calendar-grid">
      <caption className="sr-only">{month.label}</caption>
      <thead>
        <tr>
          {WEEKDAYS.map((day, i) => (
            // The short labels repeat (S, T, S, T), so the accessible name comes
            // from the full weekday name rather than the visible letter.
            <th key={i} scope="col" abbr={day.full}>
              <span aria-hidden="true">{day.short}</span>
              <span className="sr-only">{day.full}</span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {month.weeks.map((week, wi) => (
          <tr key={wi}>
            {week.map((day, di) => {
              if (day === null) return <td key={di} className="calendar-cell calendar-cell-pad" />

              const occasion = marked.get(day)
              const isToday = isCurrentMonth && today.getDate() === day
              const isPast = isCurrentMonth && day < today.getDate()

              const classes = [
                'calendar-cell',
                occasion ? 'calendar-cell-marked' : '',
                occasion && !occasion.event.is_active ? 'calendar-cell-paused' : '',
                isToday ? 'calendar-cell-today' : '',
                isPast ? 'calendar-cell-past' : '',
              ]
                .filter(Boolean)
                .join(' ')

              return (
                <td key={di} className={classes}>
                  <span className="calendar-day">{day}</span>
                  {occasion && (
                    <>
                      <span className="calendar-dot" aria-hidden="true" />
                      <span className="sr-only">{occasion.event.title}</span>
                    </>
                  )}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/**
 * The calendar: a rolling twelve months of occasions, each month a compact grid
 * with its dates listed beside it (T6.x).
 *
 * Read-only by design — creating and editing live on the agenda, and duplicating
 * that here would mean two places to keep the event form correct.
 */
export default function CalendarPage() {
  const { data: events, isLoading, isError, refetch } = useEvents()

  // One `now` for the whole render, so the grid and every countdown agree even
  // if the component happens to render across midnight.
  const today = useMemo(() => new Date(), [])
  const months = useMemo(() => buildMonthRail(events ?? [], today), [events, today])

  const total = events?.length ?? 0

  return (
    <div className="calendar-page">
      <header className="events-header">
        <p className="events-subtitle">
          The next twelve months. Marked days are occasions you track.
        </p>
      </header>

      {isLoading && <p className="events-status">Loading your calendar…</p>}

      {isError && (
        <div className="events-status events-error">
          <p>Could not load your calendar.</p>
          <button type="button" className="btn-secondary" onClick={() => void refetch()}>
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && total === 0 && (
        <div className="events-empty">
          <h2>Nothing on the calendar yet</h2>
          <p>Add an occasion and it will appear here on the day it falls.</p>
          <Link to="/app" className="btn-primary">
            Add an occasion
          </Link>
        </div>
      )}

      {!isLoading && !isError && total > 0 && (
        <ol className="calendar-rail">
          {months.map((month) => (
            <li key={month.key} className="calendar-month">
              <h2 className="events-section-label">{month.label}</h2>

              <div className="calendar-month-body">
                <MonthGrid month={month} today={today} />

                {month.occasions.length === 0 ? (
                  <p className="calendar-quiet">Nothing this month.</p>
                ) : (
                  <ul className="calendar-occasions">
                    {month.occasions.map((occasion) => (
                      <li
                        key={occasion.event.id}
                        className={
                          occasion.event.is_active && !occasion.isPast
                            ? 'calendar-occasion'
                            : 'calendar-occasion calendar-occasion-muted'
                        }
                      >
                        <span className="calendar-occasion-day mono">{occasion.day}</span>
                        <span className="calendar-occasion-main">
                          <span className="calendar-occasion-title">{occasion.event.title}</span>
                          <span className="calendar-occasion-meta">
                            {TYPE_LABELS[occasion.event.event_type]}
                          </span>
                        </span>
                        <span className="calendar-occasion-when">
                          {whenLabel(occasion.daysFromToday, occasion.event.is_active)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
