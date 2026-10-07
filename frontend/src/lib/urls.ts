/**
 * Where the signed-in dashboard lives.
 *
 * The marketing page and the app ship from one build. In production the app is
 * served from its own host (`https://app.wishly.dev`), so links out of the
 * landing page must be absolute; locally both live on the dev server, so they
 * stay relative and keep client-side routing. `VITE_APP_BASE_URL` picks which.
 */

const APP_BASE_URL = (import.meta.env.VITE_APP_BASE_URL ?? '').replace(/\/+$/, '')

/** Landing target for a signed-in user. Absolute only when APP_BASE_URL is set. */
export const DASHBOARD_URL = `${APP_BASE_URL}/app`

/** True when a URL points at another origin and needs a real navigation. */
export function isExternal(url: string): boolean {
  return /^https?:\/\//.test(url)
}
