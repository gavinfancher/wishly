import { useEffect, useRef, useState } from 'react'

export type MenuItem =
  | { separator: true }
  | { separator?: false; label: string; onSelect: () => void; disabled?: boolean }

export type Menu = { label: string; items: MenuItem[] }

/**
 * The File / Help strip under the title bar. Click a menu to open it;
 * while one is open, hovering another switches to it, as in Windows. Escape or
 * a click elsewhere closes it.
 */
export default function MenuBar({ menus }: { menus: Menu[] }) {
  const [open, setOpen] = useState<number | null>(null)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open === null) return
    root.current
      ?.querySelector<HTMLButtonElement>('.menu-drop button:not(:disabled)')
      ?.focus({ preventScroll: true })

    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(null)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(null)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="menubar" role="menubar" ref={root}>
      {menus.map((menu, index) => (
        <div key={menu.label} className="menu">
          <button
            type="button"
            role="menuitem"
            aria-haspopup="menu"
            aria-expanded={open === index}
            className={`menu-title ${open === index ? 'is-open' : ''}`}
            onClick={() => setOpen(open === index ? null : index)}
            onMouseEnter={() => open !== null && setOpen(index)}
          >
            {menu.label}
          </button>

          {open === index && (
            <div className="menu-drop" role="menu" aria-label={menu.label}>
              {menu.items.map((item, i) =>
                item.separator ? (
                  <i key={`sep-${i}`} className="menu-sep" />
                ) : (
                  <button
                    key={item.label}
                    type="button"
                    role="menuitem"
                    disabled={item.disabled}
                    onClick={() => {
                      setOpen(null)
                      item.onSelect()
                    }}
                  >
                    {item.label}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
