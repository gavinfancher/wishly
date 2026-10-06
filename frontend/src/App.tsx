import { Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './routes/LandingPage.tsx'
import SignInPage from './routes/SignInPage.tsx'
import SignUpPage from './routes/SignUpPage.tsx'
import WaitlistPage from './routes/WaitlistPage.tsx'
import ProtectedLayout from './routes/ProtectedLayout.tsx'
import OnboardingGate from './routes/OnboardingGate.tsx'
import OnboardingPage from './routes/OnboardingPage.tsx'
import RemindersPage from './routes/RemindersPage.tsx'
import AccountPage from './routes/AccountPage.tsx'

export default function App() {
  return (
    <Routes>
      {/* Public marketing page */}
      <Route path="/" element={<LandingPage />} />

      {/* Auth routes — rendered by Clerk's hosted components */}
      <Route path="/sign-in/*" element={<SignInPage />} />
      <Route path="/sign-up/*" element={<SignUpPage />} />
      <Route path="/waitlist" element={<WaitlistPage />} />

      {/* Aliases for the URLs people type */}
      <Route path="/login" element={<Navigate to="/sign-in" replace />} />
      <Route path="/signup" element={<Navigate to="/sign-up" replace />} />
      <Route path="/join" element={<Navigate to="/waitlist" replace />} />

      {/* Protected app shell — all child routes require auth */}
      <Route element={<ProtectedLayout />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<OnboardingGate />}>
          <Route path="/app" element={<RemindersPage />} />
          <Route path="/app/account" element={<AccountPage />} />
        </Route>
      </Route>

      {/* Fallback: redirect unknown paths to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
