/**
 * Shared Clerk appearance, mapped onto the app's own design tokens.
 *
 * Without this Clerk renders its stock **light** card. Because `index.css` sets
 * `color-scheme: light dark` on `:root`, the browser paints native form controls
 * dark whenever the OS is in dark mode — so the card came out white with black
 * inputs inside it. Theming Clerk from the same CSS variables the rest of the app
 * uses makes the whole card agree, and it follows the OS automatically: the
 * variables are already redefined under `prefers-color-scheme: dark`, so there is
 * no theme detection in JS to keep in sync.
 */
export const clerkAppearance = {
  variables: {
    colorBackground: 'var(--card)',
    colorText: 'var(--ink)',
    colorTextSecondary: 'var(--ink-soft)',
    colorInputBackground: 'var(--paper)',
    colorInputText: 'var(--ink)',
    colorPrimary: 'var(--pen)',
    colorTextOnPrimaryBackground: '#ffffff',
    colorDanger: 'var(--pen-deep)',
    colorSuccess: 'var(--ok)',
    colorNeutral: 'var(--ink)',
    borderRadius: 'var(--radius)',
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
  },
}
