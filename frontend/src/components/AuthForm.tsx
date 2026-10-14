import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { errorDetail, isOffline } from '../lib/api.ts'
import { useWishlyAuth } from '../lib/auth-context.ts'
import { DASHBOARD_URL } from '../lib/urls.ts'

type AuthFormProps = {
  mode: 'sign-in' | 'sign-up'
}

const COPY = {
  'sign-in': {
    title: 'Sign in to Wishly',
    submit: 'Sign in',
    busy: 'Signing in…',
    switchText: 'No account yet?',
    switchLink: 'Create one',
    switchTo: '/sign-up',
  },
  'sign-up': {
    title: 'Create your Wishly account',
    submit: 'Create account',
    busy: 'Creating account…',
    switchText: 'Already have an account?',
    switchLink: 'Sign in',
    switchTo: '/sign-in',
  },
} as const

/** Email + password form shared by /sign-in and /sign-up. */
export default function AuthForm({ mode }: AuthFormProps) {
  const { isSignedIn, signIn, signUp } = useWishlyAuth()
  const navigate = useNavigate()
  const copy = COPY[mode]

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (isSignedIn) {
    return <Navigate to={DASHBOARD_URL} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await (mode === 'sign-in' ? signIn : signUp)(email.trim(), password)
      // OnboardingGate sends brand-new accounts on to /onboarding.
      navigate(DASHBOARD_URL, { replace: true })
    } catch (err) {
      setError(
        isOffline(err)
          ? 'Wishly is unreachable. Check your connection and try again.'
          : (errorDetail(err) ?? 'Something went wrong. Please try again.')
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page onboarding">
      <form className="form-panel" onSubmit={(e) => void handleSubmit(e)}>
        <div className="form-panel-head">
          <h1>{copy.title}</h1>
          <p className="form-panel-sub">
            {copy.switchText} <Link to={copy.switchTo}>{copy.switchLink}</Link>
          </p>
        </div>

        <div className="form-panel-body">
          <label className="field">
            <span className="field-label">Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="field">
            <span className="field-label">Password</span>
            <input
              type="password"
              autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
              minLength={mode === 'sign-up' ? 12 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {mode === 'sign-up' && <span className="field-hint">At least 12 characters.</span>}
          </label>

          {error && <p className="form-error">{error}</p>}
        </div>

        <div className="form-panel-actions">
          <button type="submit" className="btn-primary btn-compact" disabled={busy}>
            {busy ? copy.busy : copy.submit}
          </button>
        </div>
      </form>
    </div>
  )
}
