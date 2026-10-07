import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { Message, Window } from './Win98.tsx'

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

  const progress = Math.min(100, Math.round((waited / EXPECTED_RECOVERY_SECONDS) * 100))

  return (
    <div className="veil" role="status" aria-live="polite">
      <Window title="Wishly" icon="wishly" className="dialog dialog-wide">
        <div className="body">
          <Message icon="error">
            <p>
              <b>Our primary server is down.</b>
            </p>
            <p>
              We&rsquo;re bringing the backup online now.{' '}
              {remaining > 0
                ? `Service should be restored in under ${minutes} minute${minutes === 1 ? '' : 's'}.`
                : 'This is taking longer than usual — it should be back shortly.'}
            </p>
            <p>
              Your occasions and reminders are safe. Nothing has been lost, and scheduled e-mails
              resume automatically. This window will close by itself.
            </p>
          </Message>
          <div
            className="meter"
            role="progressbar"
            aria-label="Starting the backup server"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <i style={{ width: `${progress}%` }} />
          </div>
          <div className="row center">
            <button
              type="button"
              className="btn btn-default"
              onClick={() => void queryClient.refetchQueries()}
            >
              Retry
            </button>
          </div>
        </div>
      </Window>
    </div>
  )
}
