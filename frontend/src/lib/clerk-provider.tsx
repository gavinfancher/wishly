import type { ReactNode } from 'react'
import { ClerkProvider } from '@clerk/clerk-react'

import { useClerkAppearance } from './clerk-appearance.ts'

/**
 * <ClerkProvider> with the app's palette attached, re-read when the OS theme
 * changes. Appearance lives on the provider so every Clerk surface inherits it
 * — the UserButton popover included, which used to open as a stock white card.
 *
 * `waitlistUrl` keeps waitlist traffic inside the app. Unset, Clerk sends it to
 * the hosted Account Portal, whose appearance is configured in the Clerk
 * dashboard rather than here — so that page ignored the palette entirely.
 */
export function ThemedClerkProvider({
  publishableKey,
  children,
}: {
  publishableKey: string
  children: ReactNode
}) {
  const appearance = useClerkAppearance()

  return (
    <ClerkProvider publishableKey={publishableKey} appearance={appearance} waitlistUrl="/waitlist">
      {children}
    </ClerkProvider>
  )
}
