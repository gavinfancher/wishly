import { Icon, Window } from './Win98.tsx'
import { DEV_NO_AUTH } from '../lib/auth-context.ts'
import { useMe } from '../lib/hooks.ts'
import { useEscape } from '../lib/useEscape.ts'

/** File › Account Info…: who you're logged on as. Read-only, so just OK. */
export default function AccountInfoDialog({ onClose }: { onClose: () => void }) {
  const { data: profile, isLoading } = useMe()
  useEscape(onClose)

  return (
    <div className="veil" role="presentation" onClick={onClose}>
      <Window
        title="Account Info"
        icon="account"
        dialog="dialog"
        className="dialog"
        onClose={onClose}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="body">
          {profile ? (
            <>
              <div className="account-who">
                <Icon name="account" size={32} />
                <b>{profile.email}</b>
              </div>
              <hr className="etched" />
              <div className="kv">
                <span>Type:</span>
                <span>{DEV_NO_AUTH ? 'Local dev user' : 'Wishly account'}</span>
                <span>Created:</span>
                <span>
                  {new Date(profile.created_at).toLocaleDateString([], { dateStyle: 'long' })}
                </span>
              </div>
              <hr className="etched" />
              <p className="field-hint">The e-mail you signed up with. Reminders are sent here.</p>
            </>
          ) : (
            <p className="empty">
              {isLoading ? 'Loading your account…' : 'Could not load your account.'}
            </p>
          )}
          <div className="row end">
            <button type="button" className="btn btn-default" onClick={onClose} autoFocus>
              OK
            </button>
          </div>
        </div>
      </Window>
    </div>
  )
}
