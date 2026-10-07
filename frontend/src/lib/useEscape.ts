import { useEffect } from 'react'

/** Calls `onEscape` when Escape is pressed, unless `disabled` (e.g. mid-save). */
export function useEscape(onEscape: () => void, disabled = false) {
  useEffect(() => {
    if (disabled) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onEscape()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onEscape, disabled])
}
