import type { ReactNode } from 'react'
import { ClerkProvider } from '@clerk/clerk-react'

import { useClerkAppearance } from './clerk-appearance.ts'

/**
 * <ClerkProvider> with the app's palette attached, re-read when the OS theme
 * changes. Appearance lives on the provider so every Clerk surface inherits it
 * — the UserButton popover included, which used to open as a stock white card.
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
    <ClerkProvider publishableKey={publishableKey} appearance={appearance}>
      {children}
    </ClerkProvider>
  )
}
