import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.tsx'
import { missingEnvVars } from './lib/env.ts'
import { AuthProvider } from './lib/auth.tsx'
import SetupScreen from './routes/SetupScreen.tsx'
import './index.css'

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

  root.render(
    <StrictMode>
      {/* AuthProvider sits inside QueryClientProvider so signing in or out can
          clear the previous user's cached data. */}
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>
  )
}
