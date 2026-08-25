/**
 * Shared Clerk appearance, mapped onto the app's own design tokens.
 *
 * Without this Clerk renders its stock **light** card. Because `index.css` sets
 * `color-scheme: light dark` on `:root`, the browser paints native form controls
 * dark whenever the OS is in dark mode — so the card came out white with black
 * inputs inside it.
 *
 * The tokens are read off `:root` as literal colors rather than handed to Clerk
 * as `var(...)` strings. Clerk parses these values to derive its own shades —
 * hover states, dividers, alpha ramps, the radius scale — and it cannot parse a
 * CSS variable, so a var() silently drops it back to defaults built for a light
 * card. That is how the "Primary" badge ended up at #25252b on a #1d1d22 card.
 * Resolving them here keeps `index.css` the single source of truth and still
 * gives Clerk something it can compute with.
 *
 * `elements` below can keep using var(): those are passed through to CSS as
 * written, and nothing is derived from them.
 *
 * Clerk's own `dark` base theme rides underneath in dark mode, the way the
 * gavinf portal pins it. It is what makes the surfaces Clerk styles but we
 * never name — dividers, dropdown rows, icon fills — come out dark; the tokens
 * above then paint the parts that should look like Wishly rather than Clerk.
 */
import { useEffect, useState } from 'react'
import { dark } from '@clerk/themes'

/** Light-mode values from `index.css`, for the first paint and for SSR. */
const FALLBACK: Record<string, string> = {
  '--card': '#ffffff',
  '--paper': '#fafaf8',
  '--ink': '#1b1b1f',
  '--ink-soft': '#6d6d75',
  '--line': '#e8e7e2',
  '--surface': '#f2f1ee',
  '--pen': '#c93b2b',
  '--pen-deep': '#a92e20',
  '--ok': '#2c7a4b',
  '--ring': 'rgb(201 59 43 / 0.18)',
  '--radius': '10px',
}

function prefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function token(name: string): string {
  if (typeof window === 'undefined') return FALLBACK[name]
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || FALLBACK[name]
}

export function buildClerkAppearance() {
  return {
    baseTheme: prefersDark() ? dark : undefined,
    variables: {
      colorBackground: token('--card'),
      colorText: token('--ink'),
      colorTextSecondary: token('--ink-soft'),
      colorInputBackground: token('--paper'),
      colorInputText: token('--ink'),
      colorPrimary: token('--pen'),
      colorTextOnPrimaryBackground: '#ffffff',
      colorDanger: token('--pen-deep'),
      colorSuccess: token('--ok'),
      colorNeutral: token('--ink'),
      colorBorder: token('--line'),
      colorMuted: token('--surface'),
      colorMutedForeground: token('--ink-soft'),
      colorRing: token('--ring'),
      borderRadius: token('--radius'),
      fontFamily: 'var(--font-sans)',
    },
    elements: {
      card: {
        backgroundColor: 'var(--card)',
        border: '1px solid var(--line)',
        boxShadow: 'var(--shadow-pop)',
      },
      // Clerk renders the "Already have an account?" strip and the "Secured by"
      // bar as separate surfaces below the card; left alone they stay near-white.
      footer: { backgroundColor: 'var(--surface)', borderTop: '1px solid var(--line)' },
      footerAction: { backgroundColor: 'var(--surface)' },
      formFieldInput: {
        backgroundColor: 'var(--paper)',
        borderColor: 'var(--line)',
        color: 'var(--ink)',
      },
      socialButtonsBlockButton: {
        backgroundColor: 'var(--paper)',
        borderColor: 'var(--line)',
        color: 'var(--ink)',
      },
      // The account menu is its own surface, not the auth card, so it needs the
      // same three treatments spelled out again.
      userButtonPopoverCard: {
        backgroundColor: 'var(--card)',
        border: '1px solid var(--line)',
        boxShadow: 'var(--shadow-pop)',
      },
      userButtonPopoverFooter: {
        backgroundColor: 'var(--surface)',
        borderTop: '1px solid var(--line)',
      },
      userButtonPopoverActionButton: { color: 'var(--ink)' },
      badge: {
        backgroundColor: 'var(--wash)',
        color: 'var(--ink-soft)',
        border: '1px solid transparent',
      },
      badge__primary: {
        backgroundColor: 'var(--pen-tint)',
        color: 'var(--pen)',
      },
    },
  }
}

/**
 * The resolved colors are a snapshot, so they have to be re-read when the OS
 * flips light/dark. The app has no theme toggle of its own — `index.css` swaps
 * the tokens under `prefers-color-scheme` — so that media query is the only
 * signal to watch.
 */
export function useClerkAppearance() {
  const [appearance, setAppearance] = useState(buildClerkAppearance)

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const reread = () => setAppearance(buildClerkAppearance())
    // Re-read once on mount too: the first build can run before the stylesheet
    // is applied, in which case it used the light fallbacks.
    reread()
    query.addEventListener('change', reread)
    return () => query.removeEventListener('change', reread)
  }, [])

  return appearance
}
