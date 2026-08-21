import { useQueryClient } from '@tanstack/react-query'

/**
 * Shown when the API cannot be reached at all — the tunnel is down, the host
 * machine is asleep, or there is no network.
 *
 * This is deliberately distinct from an API error: a 500 means Wishly answered
 * and something is broken; no answer at all usually means the backend simply
 * isn't running right now. Telling the user to "refresh" in that case is wrong —
 * refreshing changes nothing until the host is back.
 */
export default function ServiceUnavailable() {
  const queryClient = useQueryClient()

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

        <h2>Wishly is offline right now</h2>
        <p>
          The app can&rsquo;t reach its server. Your occasions and reminders are safe — nothing
          has been lost, and scheduled emails resume automatically once it&rsquo;s back.
        </p>

        <button
          type="button"
          className="btn-primary"
          onClick={() => void queryClient.refetchQueries()}
        >
          Try again
        </button>
      </div>
    </div>
  )
}
