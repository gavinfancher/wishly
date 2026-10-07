import { useId, useState } from 'react'
import type { HTMLAttributes, ReactNode } from 'react'

import { effectiveTheme, saveTheme } from '../lib/theme.ts'

/**
 * Windows 98 building blocks: the icon set and window chrome every screen is
 * drawn with. Icons are tiny hand-drawn SVGs on a 16 / 20 / 32 grid so they
 * stay crisp at 1x, the way the real ones were bitmaps.
 */

const ICONS = {
  // The Wishly mark: a calendar page with the date circled in red.
  wishly: (
    <svg viewBox="0 0 16 16">
      <path d="M1.5 2.5h13v12h-13z" fill="#fff" stroke="#000" />
      <path d="M2 3h12v3H2z" fill="#000080" />
      <path d="M4.5 1v3M11.5 1v3" stroke="#000" />
      <path d="M7 9l1.5-1v4.5" fill="none" stroke="#000" />
      <ellipse cx="8" cy="10.3" rx="4.6" ry="3.1" fill="none" stroke="#d40000" strokeWidth="1.2" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 16 16">
      <path d="M1.5 2.5h13v12h-13z" fill="#fff" stroke="#000" />
      <path d="M2 3h12v3H2z" fill="#d40000" />
      <path d="M4.5 1v3M11.5 1v3" stroke="#000" />
      <path d="M4 8h2v2H4zM7 8h2v2H7zM10 8h2v2h-2zM4 11h2v2H4zM7 11h2v2H7z" fill="#808080" />
    </svg>
  ),
  computer: (
    <svg viewBox="0 0 16 16">
      <path d="M1.5 1.5h13v9h-13z" fill="#c0c0c0" stroke="#000" />
      <path d="M3 3h10v6H3z" fill="#008080" />
      <path d="M4.5 12.5h7v2h-7z" fill="#c0c0c0" stroke="#000" />
      <path d="M6 10.5v2M10 10.5v2" stroke="#000" />
    </svg>
  ),
  account: (
    <svg viewBox="0 0 16 16">
      <circle cx="8" cy="5" r="3" fill="#ffdcb0" stroke="#000" />
      <path d="M2.5 15c0-4 2.5-6 5.5-6s5.5 2 5.5 6z" fill="#000080" stroke="#000" />
    </svg>
  ),
  mail: (
    <svg viewBox="0 0 16 16">
      <path d="M1.5 3.5h13v9h-13z" fill="#fff" stroke="#000" />
      <path d="M1.5 3.5l6.5 5 6.5-5" fill="none" stroke="#000" />
    </svg>
  ),
  help: (
    <svg viewBox="0 0 16 16">
      <path d="M2.5 1.5h9l2 2v11h-11z" fill="#ffd95a" stroke="#000" />
      <path d="M6 6c0-3 4-3 4 0 0 2-2 1.5-2 4" fill="none" stroke="#000080" strokeWidth="1.6" />
      <circle cx="8" cy="12.3" r="1" fill="#000080" />
    </svg>
  ),
  key: (
    <svg viewBox="0 0 16 16">
      <circle cx="5" cy="8" r="3.5" fill="#ffd95a" stroke="#000" />
      <circle cx="4.5" cy="8" r="1" fill="#000" />
      <path d="M8.5 7.5H15v2h-1.5V11h-2V9.5h-3z" fill="#ffd95a" stroke="#000" />
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 16 16">
      <circle cx="8" cy="8" r="6.5" fill="#fff" stroke="#000" />
      <path d="M8 4v4h3" fill="none" stroke="#000080" strokeWidth="1.5" />
    </svg>
  ),
  new: (
    <svg viewBox="0 0 20 20">
      <path d="M2.5 5.5h12v12h-12z" fill="#fff" stroke="#000" />
      <path d="M3 6h11v3H3z" fill="#d40000" />
      <path d="M5 11h2v2H5zM8.5 11h2v2h-2zM5 14h2v2H5z" fill="#808080" />
      <path d="M16 1v6M13 4h6M14 2l4 4M18 2l-4 4" stroke="#d40000" />
    </svg>
  ),
  props: (
    <svg viewBox="0 0 20 20">
      <path d="M3.5 1.5h9l3 3v14h-12z" fill="#fff" stroke="#000" />
      <path d="M6 6h6M6 8.5h6M6 11h3" stroke="#000080" />
      <path d="M8 17l1-3.5 7.5-7.5 2.5 2.5-7.5 7.5z" fill="#ffd95a" stroke="#000" />
    </svg>
  ),
  delete: (
    <svg viewBox="0 0 20 20">
      <path d="M4 4l12 12M16 4 4 16" stroke="#d40000" strokeWidth="3" />
    </svg>
  ),
  logoff: (
    <svg viewBox="0 0 20 20">
      <path d="M3.5 2.5h9v15h-9z" fill="#c0c0c0" stroke="#000" />
      <path d="M5 4h6v12H5z" fill="#000080" />
      <path d="M10 10h8m-3-3 3 3-3 3" fill="none" stroke="#000" strokeWidth="1.6" />
    </svg>
  ),
  info: (
    <svg viewBox="0 0 32 32">
      <circle cx="16" cy="15" r="13" fill="#fff" stroke="#000" />
      <path d="M13 27l-3 4 8-4" fill="#fff" stroke="#000" />
      <path d="M16 13v9" stroke="#000080" strokeWidth="4" />
      <circle cx="16" cy="8" r="2.3" fill="#000080" />
    </svg>
  ),
  ask: (
    <svg viewBox="0 0 32 32">
      <circle cx="16" cy="15" r="13" fill="#fff" stroke="#000" />
      <path d="M13 27l-3 4 8-4" fill="#fff" stroke="#000" />
      <path d="M11 11c0-6 10-6 10 0 0 4-5 3-5 8" fill="none" stroke="#000080" strokeWidth="3.5" />
      <circle cx="16" cy="23" r="2.2" fill="#000080" />
    </svg>
  ),
  warn: (
    <svg viewBox="0 0 32 32">
      <path d="M16 2 31 29H1z" fill="#ffd95a" stroke="#000" strokeLinejoin="round" />
      <path d="M16 10v10" stroke="#000" strokeWidth="3.5" />
      <circle cx="16" cy="24.5" r="2" fill="#000" />
    </svg>
  ),
  error: (
    <svg viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="14" fill="#d40000" stroke="#000" />
      <path d="M10 10l12 12M22 10 10 22" stroke="#fff" strokeWidth="4" />
    </svg>
  ),
} as const

export type IconName = keyof typeof ICONS

/** An icon at a fixed pixel size. Decorative: the label beside it does the talking. */
export function Icon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <span className="icon" style={{ width: size, height: size }} aria-hidden="true">
      {ICONS[name]}
    </span>
  )
}

/** The little "×" on a title bar. */
function CloseGlyph() {
  return (
    <svg width="8" height="7" viewBox="0 0 8 7" aria-hidden="true">
      <path d="M0 0h2l2 2 2-2h2L5 3.5 8 7H6L4 5 2 7H0l3-3.5z" />
    </svg>
  )
}

/** Title-bar button that flips between the light and dark themes. */
export function ThemeToggle() {
  const [theme, setTheme] = useState(effectiveTheme)
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      className="tbtn"
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      onClick={() => {
        saveTheme(next)
        setTheme(next)
      }}
    >
      {theme === 'dark' ? (
        // Sun
        <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden="true">
          <path d="M3 2h3v1h1v3H6v1H3V6H2V3h1zM4 0h1v1H4zM4 8h1v1H4zM0 4h1v1H0zM8 4h1v1H8z" />
        </svg>
      ) : (
        // Moon
        <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">
          <path d="M3 0h3v1H4v1H3v4h1v1h2v1H3V7H2V6H1V2h1V1h1z" />
        </svg>
      )}
    </button>
  )
}

type TitleBarProps = {
  title: ReactNode
  icon?: IconName
  id?: string
  onClose?: () => void
  closeDisabled?: boolean
  /** Show the light/dark toggle — on the page's main window only. */
  themeToggle?: boolean
}

export function TitleBar({ title, icon, id, onClose, closeDisabled, themeToggle }: TitleBarProps) {
  return (
    <div className="titlebar">
      {icon && <Icon name={icon} />}
      <span className="titlebar-name" id={id}>
        {title}
      </span>
      {themeToggle && <ThemeToggle />}
      {onClose && (
        <button
          type="button"
          className="tbtn"
          aria-label="Close"
          onClick={onClose}
          disabled={closeDisabled}
        >
          <CloseGlyph />
        </button>
      )}
    </div>
  )
}

type WindowProps = Omit<HTMLAttributes<HTMLElement>, 'title'> & {
  title: ReactNode
  icon?: IconName
  onClose?: () => void
  closeDisabled?: boolean
  themeToggle?: boolean
  /** Renders as a dialog (role + aria-modal) labelled by its title bar. */
  dialog?: 'dialog' | 'alertdialog'
  /** Status bar text along the bottom edge. */
  status?: ReactNode
}

/** A raised gray window with a title bar, optionally a modal dialog. */
export function Window({
  title,
  icon,
  onClose,
  closeDisabled,
  themeToggle,
  dialog,
  status,
  className,
  children,
  ...rest
}: WindowProps) {
  const titleId = useId()
  const dialogProps = dialog
    ? { role: dialog, 'aria-modal': true as const, 'aria-labelledby': titleId }
    : { 'aria-labelledby': titleId }

  return (
    <section className={`window ${className ?? ''}`} {...dialogProps} {...rest}>
      <TitleBar
        title={title}
        icon={icon}
        id={titleId}
        onClose={onClose}
        closeDisabled={closeDisabled}
        themeToggle={themeToggle}
      />
      {children}
      {status !== undefined && (
        <div className="statusbar">
          <div className="statusbar-main">{status}</div>
        </div>
      )}
    </section>
  )
}

/** Icon-and-text message, the body of every Windows message box. */
export function Message({ icon, children }: { icon: IconName; children: ReactNode }) {
  return (
    <div className="msg">
      <Icon name={icon} size={32} />
      <div className="msg-text">{children}</div>
    </div>
  )
}
