import { Message, Window } from './Win98.tsx'
import { isOffline } from '../lib/api.ts'
import { useMe, useSendTestEmail } from '../lib/hooks.ts'
import { useEscape } from '../lib/useEscape.ts'

/**
 * File › Send Test E-mail…: asks first (Send / Cancel), then reports how it went
 * in the same box, the way Windows message boxes chain.
 */
export default function TestEmailDialog({ onClose }: { onClose: () => void }) {
  const { data: profile } = useMe()
  const send = useSendTestEmail()
  useEscape(onClose, send.isPending)

  const to = profile?.email ?? 'your e-mail address'

  let icon: 'ask' | 'info' | 'error' = 'ask'
  let text = `Send a test e-mail to ${to}? It looks like a real reminder, so you can check it arrives and isn't marked as spam.`
  if (send.isSuccess) {
    icon = 'info'
    text = `A test e-mail was sent to ${to}. It should arrive within a minute.`
  } else if (send.isError) {
    icon = 'error'
    text = isOffline(send.error)
      ? 'Wishly is unreachable. Check your connection and try again.'
      : 'The test e-mail could not be sent. Please try again later.'
  }

  return (
    <div className="veil" role="presentation">
      <Window
        title="Send Test E-mail"
        icon="mail"
        dialog="alertdialog"
        className="dialog"
        onClose={onClose}
        closeDisabled={send.isPending}
      >
        <div className="body">
          <Message icon={icon}>
            <p>{text}</p>
          </Message>
          <div className="row center">
            {send.isSuccess ? (
              <button type="button" className="btn btn-default" onClick={onClose} autoFocus>
                OK
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-default"
                  onClick={() => send.mutate()}
                  disabled={send.isPending}
                  autoFocus
                >
                  {send.isPending ? 'Sending…' : send.isError ? 'Try Again' : 'Send'}
                </button>
                <button type="button" className="btn" onClick={onClose} disabled={send.isPending}>
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      </Window>
    </div>
  )
}
