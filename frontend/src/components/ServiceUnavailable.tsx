import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

/**
 * Shown when the API cannot be reached at all — no answer within five seconds.
 *
 * This is deliberately distinct from an API error: a 500 means Wishly answered
 * and something is broken; no answer at all means the backend is not there
 * right now. Telling the user to "refresh" in that case is wrong — refreshing
 * changes nothing until a server is back.
 *
 * It is also not a dead end. When the primary host goes dark a watchdog scales
 * a standby up on AWS, so the right thing for this screen to do is wait and
 * retry on the user's behalf rather than make them keep clicking. It polls
 * every five seconds and disappears by itself the moment a request succeeds.
 */

const RETRY_INTERVAL_MS = 5_000

/** Roughly how long a failover takes end to end: detection, then the standby starting. */
const EXPECTED_RECOVERY_SECONDS = 300

export default function ServiceUnavailable() {
  const queryClient = useQueryClient()
  const [waited, setWaited] = useState(0)

  useEffect(() => {
    // Retry in the background. react-query dedupes and the fetch itself has a
    // 5s timeout, so these cannot pile up.
    const id = setInterval(() => {
      setWaited((s) => s + RETRY_INTERVAL_MS / 1000)
      void queryClient.refetchQueries()
    }, RETRY_INTERVAL_MS)
    return () => clearInterval(id)
  }, [queryClient])

  const remaining = Math.max(0, EXPECTED_RECOVERY_SECONDS - waited)
  const minutes = Math.ceil(remaining / 60)

  return (
    <div className="service-down" role="status" aria-live="polite">
      <div className="service-down-card">
        <span className="service-down-mark" aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3a9 9 0 1 0 9 9" />
            <path d="M12 8v5" />
            <circle cx="12" cy="16.5" r="0.6" fill="currentColor" stroke="none" />
          </svg>
        </span>

        <h2>Our primary server is down</h2>
        <p>
          We&rsquo;re bringing the backup online now.{' '}
          {remaining > 0
            ? `Service should be restored in under ${minutes} minute${minutes === 1 ? '' : 's'}.`
            : 'This is taking longer than usual — it should be back shortly.'}
        </p>
        <p className="service-down-note">
          Your occasions and reminders are safe. Nothing has been lost, and scheduled emails
          resume automatically. This page will refresh itself.
        </p>

        <button
          type="button"
          className="btn-primary"
          onClick={() => void queryClient.refetchQueries()}
        >
          Try now
        </button>
      </div>
    </div>
  )
}
