/**
 * Light / dark theme. Follows the OS by default; the title-bar toggle pins a
 * choice, kept in localStorage and applied as `data-theme` on <html>.
 */

export type Theme = 'light' | 'dark'

const KEY = 'wishly-theme'

export function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

export function effectiveTheme(): Theme {
  return storedTheme() ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
}

export function applyTheme(theme: Theme | null) {
  if (theme) document.documentElement.dataset.theme = theme
  else delete document.documentElement.dataset.theme
}

export function saveTheme(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // Private mode or blocked storage: the choice just lasts this page view.
  }
  applyTheme(theme)
}
