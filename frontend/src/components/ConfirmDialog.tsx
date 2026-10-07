import { useEffect } from 'react'

import { Message, Window } from './Win98.tsx'

type ConfirmDialogProps = {
  title: string
  body: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  isBusy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Windows message box, replacing window.confirm. Escape cancels. */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel = 'Yes',
  cancelLabel = 'No',
  danger = false,
  isBusy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && !isBusy) onCancel()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isBusy, onCancel])

  return (
    <div className="veil" role="presentation" onClick={() => !isBusy && onCancel()}>
      <Window
        title={title}
        dialog="alertdialog"
        className="dialog"
        onClose={onCancel}
        closeDisabled={isBusy}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="body">
          <Message icon={danger ? 'warn' : 'ask'}>
            <p>{body}</p>
          </Message>
          <div className="row center">
            <button type="button" className="btn btn-default" onClick={onConfirm} disabled={isBusy}>
              {isBusy ? 'Working…' : confirmLabel}
            </button>
            <button type="button" className="btn" onClick={onCancel} disabled={isBusy} autoFocus>
              {cancelLabel}
            </button>
          </div>
        </div>
      </Window>
    </div>
  )
}
