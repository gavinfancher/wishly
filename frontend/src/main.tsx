import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ClerkProvider } from '@clerk/clerk-react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.tsx'
import { missingEnvVars } from './lib/env.ts'
import { AuthProvider } from './lib/auth.tsx'
import { DEV_NO_AUTH } from './lib/auth-context.ts'
import SetupScreen from './routes/SetupScreen.tsx'
import './index.css'

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
const setupMissing = missingEnvVars()

const root = createRoot(document.getElementById('root')!)

if (setupMissing.length > 0) {
  root.render(
    <StrictMode>
      <SetupScreen missing={setupMissing} />
    </StrictMode>
  )
} else {
  const queryClient = new QueryClient()

  const appTree = (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  )

  root.render(
    <StrictMode>
      {DEV_NO_AUTH ? (
        appTree
      ) : (
        <ClerkProvider publishableKey={publishableKey!}>{appTree}</ClerkProvider>
      )}
    </StrictMode>
  )
}
