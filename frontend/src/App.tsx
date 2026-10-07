import { Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './routes/LandingPage.tsx'
import SignInPage from './routes/SignInPage.tsx'
import SignUpPage from './routes/SignUpPage.tsx'
import ProtectedLayout from './routes/ProtectedLayout.tsx'
import OnboardingGate from './routes/OnboardingGate.tsx'
import OnboardingPage from './routes/OnboardingPage.tsx'
import RemindersPage from './routes/RemindersPage.tsx'

export default function App() {
  return (
    <Routes>
      {/* Public marketing page */}
      <Route path="/" element={<LandingPage />} />

      {/* Email + password, against the API's /auth endpoints */}
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/sign-up" element={<SignUpPage />} />

      {/* Aliases for the URLs people type */}
      <Route path="/login" element={<Navigate to="/sign-in" replace />} />
      <Route path="/signup" element={<Navigate to="/sign-up" replace />} />

      {/* Protected app shell — all child routes require auth */}
      <Route element={<ProtectedLayout />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<OnboardingGate />}>
          <Route path="/app" element={<RemindersPage />} />
          {/* Same window with File › Account Info open over the list. */}
          <Route path="/app/account" element={<RemindersPage />} />
        </Route>
      </Route>

      {/* Fallback: redirect unknown paths to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
