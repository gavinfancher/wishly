import { useEffect, useRef, useState } from 'react'

type MenuItem = {
  label: string
  onSelect: () => void
  danger?: boolean
  disabled?: boolean
}

type RowMenuProps = {
  /** Used in the trigger's accessible name, e.g. "More actions for Mom's Bday". */
  label: string
  items: MenuItem[]
}

/**
 * Kebab menu for secondary row actions.
 *
 * Row actions were three always-visible buttons, which made every row shout its
 * least-used operations — and put Delete one stray click from the row's primary
 * action. Folding them behind a menu leaves the countdown as the only thing
 * competing with the title.
 */
export default function RowMenu({ label, items }: RowMenuProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="row-menu" ref={root}>
      <button
        type="button"
        className="row-menu-trigger"
        aria-label={`More actions for ${label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
          <circle cx="8" cy="3" r="1.4" />
          <circle cx="8" cy="8" r="1.4" />
          <circle cx="8" cy="13" r="1.4" />
        </svg>
      </button>

      {open && (
        <div className="row-menu-popover" role="menu">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={`row-menu-item ${item.danger ? 'row-menu-item-danger' : ''}`}
              disabled={item.disabled}
              onClick={() => {
                setOpen(false)
                item.onSelect()
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
