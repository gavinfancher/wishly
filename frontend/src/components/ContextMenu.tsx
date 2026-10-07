import { useEffect, useRef } from 'react'

export type ContextMenuItem = {
  label: string
  onSelect: () => void
  /** The default action, shown bold — what double-click does. */
  bold?: boolean
  disabled?: boolean
}

type ContextMenuProps = {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}

/**
 * Right-click menu at the pointer. Closes on Escape, on a click elsewhere,
 * or on scroll/resize (it is fixed-positioned and would drift off its row).
 */
export default function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    root.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()

    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) onClose()
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', onClose)
    window.addEventListener('scroll', onClose, true)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('resize', onClose)
      window.removeEventListener('scroll', onClose, true)
    }
  }, [onClose])

  // Keep the menu on screen near the right and bottom edges.
  const left = Math.min(x, window.innerWidth - 170)
  const top = Math.min(y, window.innerHeight - (items.length * 24 + 12))

  return (
    <div className="ctx" role="menu" ref={root} style={{ left, top }}>
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          className={item.bold ? 'is-bold' : undefined}
          disabled={item.disabled}
          onClick={() => {
            onClose()
            item.onSelect()
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
