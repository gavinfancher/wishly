import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Icon, Window } from './Win98.tsx'
import { errorDetail, isOffline } from '../lib/api.ts'
import { useWishlyAuth } from '../lib/auth-context.ts'
import { DASHBOARD_URL } from '../lib/urls.ts'

type AuthFormProps = {
  mode: 'sign-in' | 'sign-up'
}

const COPY = {
  'sign-in': {
    title: 'Log On to Wishly',
    prompt: 'Type your e-mail address and password to log on to Wishly.',
    busy: 'Logging on…',
    switchText: 'No account yet?',
    switchLink: 'Create one',
    switchTo: '/sign-up',
  },
  'sign-up': {
    title: 'Create Wishly Account',
    prompt: 'Type an e-mail address and choose a password for your new Wishly account.',
    busy: 'Creating…',
    switchText: 'Already have an account?',
    switchLink: 'Log on',
    switchTo: '/sign-in',
  },
} as const

/** Email + password form shared by /sign-in and /sign-up. */
export default function AuthForm({ mode }: AuthFormProps) {
  const { isSignedIn, signIn, signUp } = useWishlyAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const copy = COPY[mode]

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (isSignedIn) {
    return <Navigate to={DASHBOARD_URL} replace />
  }

  // Back to the previous page; a link opened directly has no history here, so go home.
  function goBack() {
    if (location.key === 'default') navigate('/')
    else navigate(-1)
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
    <div className="screen screen-center">
      <Window
        title={copy.title}
        icon="key"
        dialog="dialog"
        className="dialog logon"
        themeToggle
        onClose={goBack}
        closeDisabled={busy}
      >
        <form className="body" onSubmit={(e) => void handleSubmit(e)}>
          <div className="logon-grid">
            <Icon name="key" size={32} />
            <div className="logon-fields">
              <p>{copy.prompt}</p>
              <label className="field-row">
                <span>E-mail:</span>
                <input
                  className="text"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                />
              </label>
              <label className="field-row">
                <span>Password:</span>
                <input
                  className="text"
                  type="password"
                  autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
                  minLength={mode === 'sign-up' ? 12 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {mode === 'sign-up' && (
                <p className="field-hint">Passwords must be at least 12 characters.</p>
              )}
            </div>
            <div className="logon-buttons">
              <button type="submit" className="btn btn-default" disabled={busy}>
                {busy ? copy.busy : 'OK'}
              </button>
              <button type="button" className="btn" onClick={goBack} disabled={busy}>
                &lt; Back
              </button>
            </div>
          </div>

          {error && <p className="form-error">{error}</p>}

          <p className="logon-switch">
            {copy.switchText} <Link to={copy.switchTo}>{copy.switchLink}</Link>
          </p>
        </form>
      </Window>
    </div>
  )
}
