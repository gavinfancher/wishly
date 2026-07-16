import { useEffect } from 'react'

type ConfirmDialogProps = {
  title: string
  body: string
  confirmLabel: string
  danger?: boolean
  isBusy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Modal confirmation, replacing window.confirm. Escape cancels. */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
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
    <div className="modal-overlay" role="presentation" onClick={() => !isBusy && onCancel()}>
      <div
        className="modal-panel modal-panel-sm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-title" className="dialog-title">
          {title}
        </h2>
        <p className="dialog-body">{body}</p>
        <div className="form-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onCancel}
            disabled={isBusy}
            autoFocus
          >
            Cancel
          </button>
          <button
            type="button"
            className={danger ? 'btn-danger' : 'btn-primary'}
            onClick={onConfirm}
            disabled={isBusy}
          >
            {isBusy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
