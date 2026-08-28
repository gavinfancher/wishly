import { Routes, Route, Navigate } from 'react-router-dom'
import LandingPage from './routes/LandingPage.tsx'
import SignInPage from './routes/SignInPage.tsx'
import SignUpPage from './routes/SignUpPage.tsx'
import ProtectedLayout from './routes/ProtectedLayout.tsx'
import OnboardingGate from './routes/OnboardingGate.tsx'
import OnboardingPage from './routes/OnboardingPage.tsx'
import EventsPage from './routes/EventsPage.tsx'
import CalendarPage from './routes/CalendarPage.tsx'
import HistoryPage from './routes/HistoryPage.tsx'
import AccountPage from './routes/AccountPage.tsx'
import PreferencesPage from './routes/PreferencesPage.tsx'

export default function App() {
  return (
    <Routes>
      {/* Public marketing page */}
      <Route path="/" element={<LandingPage />} />

      {/* Auth routes — rendered by Clerk's hosted components */}
      <Route path="/sign-in/*" element={<SignInPage />} />
      <Route path="/sign-up/*" element={<SignUpPage />} />

      {/* Aliases for the URLs people type */}
      <Route path="/login" element={<Navigate to="/sign-in" replace />} />
      <Route path="/signup" element={<Navigate to="/sign-up" replace />} />

      {/* Public preferences page (linked from emails); auth optional */}
      <Route path="/preferences" element={<PreferencesPage />} />

      {/* Protected app shell — all child routes require auth */}
      <Route element={<ProtectedLayout />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<OnboardingGate />}>
          <Route path="/app" element={<EventsPage />} />
          <Route path="/app/calendar" element={<CalendarPage />} />
          <Route path="/app/history" element={<HistoryPage />} />
          <Route path="/app/account" element={<AccountPage />} />
        </Route>
      </Route>

      {/* Fallback: redirect unknown paths to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
