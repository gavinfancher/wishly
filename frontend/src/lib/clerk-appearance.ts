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
 *
 * This is passed to <ClerkProvider>, not to individual components, so every
 * Clerk surface inherits it — including the UserButton popover, which used to
 * open as a stock white card over the dark app.
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
    // Clerk derives its own hairlines, hovers, and focus rings when these are
    // left out, and those derivations are what made the card read as a
    // different product even once the background matched.
    colorBorder: 'var(--line)',
    colorMuted: 'var(--surface)',
    colorMutedForeground: 'var(--ink-soft)',
    colorRing: 'var(--ring)',
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
  },
}
